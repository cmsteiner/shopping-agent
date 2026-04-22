"""Shopping trip service."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Item, ShoppingList, ShoppingTrip
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus
from app.models.shopping_trip import TripStatus
from app.services.realtime_service import record_event


def _serialize_trip(trip: ShoppingTrip) -> dict:
    return {
        "id": trip.id,
        "status": trip.status.value,
        "started_at": trip.started_at.isoformat().replace("+00:00", "Z") if trip.started_at else None,
        "completed_at": trip.completed_at.isoformat().replace("+00:00", "Z") if trip.completed_at else None,
        "version": trip.version,
    }


def _serialize_list(shopping_list: ShoppingList) -> dict:
    return {
        "id": shopping_list.id,
        "status": shopping_list.status.value,
        "version": shopping_list.version,
        "created_at": shopping_list.created_at.isoformat().replace("+00:00", "Z") if shopping_list.created_at else None,
    }


def _serialize_item(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": str(item.quantity) if item.quantity is not None else None,
        "unit": item.unit,
        "notes": item.notes,
        "category_id": item.category_id,
        "category_name": item.category or "Uncategorized",
        "status": item.status.value,
        "is_purchased": item.is_purchased,
        "new_during_trip": item.new_during_trip,
        "version": item.version,
        "created_at": item.created_at.isoformat().replace("+00:00", "Z") if item.created_at else None,
        "updated_at": item.updated_at.isoformat().replace("+00:00", "Z") if item.updated_at else None,
    }


def _get_active_list(db: Session) -> ShoppingList | None:
    return (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.ACTIVE)
        .first()
    )


def get_active_trip(db: Session) -> ShoppingTrip | None:
    """Return the active trip for the current active list, if any."""
    active_list = _get_active_list(db)
    if active_list is None:
        return None

    return (
        db.query(ShoppingTrip)
        .filter(
            ShoppingTrip.list_id == active_list.id,
            ShoppingTrip.status == TripStatus.ACTIVE,
        )
        .first()
    )


def start_trip(db: Session) -> ShoppingTrip:
    """Start a shopping trip for the current active list."""
    active_list = _get_active_list(db)
    if active_list is None:
        raise ValueError("No ACTIVE list found.")

    existing_trip = get_active_trip(db)
    if existing_trip is not None:
        raise ValueError("A shopping trip is already in progress.")

    has_items = (
        db.query(Item)
        .filter(
            Item.list_id == active_list.id,
            Item.status == ItemStatus.ACTIVE,
        )
        .first()
    )
    if has_items is None:
        raise ValueError("A shopping trip can only be started when the list has at least one item.")

    trip = ShoppingTrip(list_id=active_list.id, status=TripStatus.ACTIVE)
    db.add(trip)
    db.flush()
    record_event(
        list_id=active_list.id,
        event_type="trip.started",
        entity_type="trip",
        entity_id=trip.id,
        payload={"trip": _serialize_trip(trip)},
        db=db,
    )
    db.commit()
    db.refresh(trip)
    return trip


def prepare_finish_trip(trip_id: int, db: Session) -> tuple[ShoppingTrip, list[Item]]:
    """Return the active trip and its unchecked active items."""
    trip = db.query(ShoppingTrip).filter(ShoppingTrip.id == trip_id).first()
    if trip is None:
        raise ValueError(f"Trip with id={trip_id} not found.")
    if trip.status != TripStatus.ACTIVE:
        raise ValueError("Only an active trip can be prepared for completion.")

    unchecked_items = (
        db.query(Item)
        .filter(
            Item.list_id == trip.list_id,
            Item.status == ItemStatus.ACTIVE,
            Item.is_purchased.is_(False),
        )
        .order_by(Item.id)
        .all()
    )
    return trip, unchecked_items


def complete_finish_trip(
    trip_id: int,
    carryover_items: list[dict],
    db: Session,
) -> tuple[ShoppingTrip, ShoppingList, ShoppingList, list[Item]]:
    """Complete a trip, archive its list, create a new active list, and carry over selected items."""
    trip = db.query(ShoppingTrip).filter(ShoppingTrip.id == trip_id).first()
    if trip is None:
        raise ValueError(f"Trip with id={trip_id} not found.")
    if trip.status != TripStatus.ACTIVE:
        raise ValueError("Only an active trip can be completed.")

    archived_list = db.query(ShoppingList).filter(ShoppingList.id == trip.list_id).first()
    if archived_list is None:
        raise ValueError(f"List with id={trip.list_id} not found.")

    unchecked_items = (
        db.query(Item)
        .filter(
            Item.list_id == trip.list_id,
            Item.status == ItemStatus.ACTIVE,
            Item.is_purchased.is_(False),
        )
        .order_by(Item.id)
        .all()
    )
    carryover_map = {entry["item_id"]: bool(entry.get("carry_over")) for entry in carryover_items}

    trip.status = TripStatus.COMPLETED
    trip.completed_at = datetime.now(timezone.utc)
    trip.version += 1

    archived_list.status = ListStatus.ARCHIVED
    archived_list.archived_at = datetime.now(timezone.utc)
    archived_list.version += 1

    new_list = ShoppingList(status=ListStatus.ACTIVE)
    db.add(new_list)
    db.flush()

    carried: list[Item] = []
    for item in unchecked_items:
        if not carryover_map.get(item.id, False):
            continue
        new_item = Item(
            list_id=new_list.id,
            name=item.name,
            quantity=item.quantity,
            unit=item.unit,
            brand_pref=item.brand_pref,
            category=item.category,
            category_id=item.category_id,
            notes=item.notes,
            status=ItemStatus.ACTIVE,
            is_purchased=False,
            purchased_at=None,
            new_during_trip=False,
            added_by=item.added_by,
        )
        db.add(new_item)
        carried.append(new_item)

    record_event(
        list_id=archived_list.id,
        event_type="trip.completed",
        entity_type="trip",
        entity_id=trip.id,
        payload={"trip": _serialize_trip(trip)},
        db=db,
    )
    record_event(
        list_id=new_list.id,
        event_type="list.replaced",
        entity_type="list",
        entity_id=new_list.id,
        payload={
            "archived_list_id": archived_list.id,
            "new_active_list": _serialize_list(new_list),
            "carried_over_items": [_serialize_item(item) for item in carried],
        },
        db=db,
    )

    db.commit()
    db.refresh(trip)
    db.refresh(archived_list)
    db.refresh(new_list)
    for item in carried:
        db.refresh(item)

    return trip, archived_list, new_list, carried
