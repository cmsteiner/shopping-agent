"""Item service — create and manage shopping list items."""
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.models import Category, Item, PendingConfirmation, ShoppingList, ShoppingTrip
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus
from app.models.shopping_trip import TripStatus
from app.services import brand_service
from app.services.realtime_service import record_event


def _get_or_create_active_list(db: Session) -> ShoppingList:
    """Return the current ACTIVE shopping list, creating one if needed."""
    shopping_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.ACTIVE)
        .first()
    )
    if shopping_list is None:
        shopping_list = ShoppingList(status=ListStatus.ACTIVE)
        db.add(shopping_list)
        db.flush()
    return shopping_list


def add_items(
    items: list[dict],
    list_id: int | None,
    user_id: int,
    db: Session,
) -> list[Item]:
    """
    Create Item records from a list of dicts and commit them.

    Each dict may contain: name (required), quantity, unit, brand_hint, category.
    If list_id is None, the current ACTIVE list is used (or a new one is created).
    """
    if list_id is None:
        shopping_list = _get_or_create_active_list(db)
        list_id = shopping_list.id

    active_trip = (
        db.query(ShoppingTrip)
        .filter(
            ShoppingTrip.list_id == list_id,
            ShoppingTrip.status == TripStatus.ACTIVE,
        )
        .first()
    )

    created = []
    for item_data in items:
        # Use explicit brand if provided; otherwise look up stored preference.
        explicit_brand = item_data.get("brand_hint") or item_data.get("brand_pref")
        if not explicit_brand:
            pref = brand_service.get_brand_preference(item_data["name"].lower(), db)
            auto_brand = pref.brand if pref is not None else None
        else:
            auto_brand = None

        quantity = item_data.get("quantity")
        if quantity in (None, ""):
            quantity = 1

        category_id = item_data.get("category_id")
        if category_id in ("", None):
            category_id = None

        category_name = item_data.get("category")
        if category_id is not None and not category_name:
            category = db.query(Category).filter(Category.id == category_id).first()
            if category is not None:
                category_name = category.name

        item = Item(
            list_id=list_id,
            name=item_data["name"],
            quantity=quantity,
            unit=item_data.get("unit"),
            brand_pref=explicit_brand or auto_brand,
            category=category_name,
            category_id=category_id,
            notes=item_data.get("notes"),
            status=ItemStatus.ACTIVE,
            added_by=user_id,
            new_during_trip=active_trip is not None,
        )
        db.add(item)
        db.flush()
        record_event(
            list_id=item.list_id,
            event_type="item.created",
            entity_type="item",
            entity_id=item.id,
            payload={
                "item": {
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
            },
            db=db,
        )
        created.append(item)

    db.commit()
    for item in created:
        db.refresh(item)

    return created


def hold_pending(
    item_dict: dict,
    existing_item_id: int,
    triggered_by: int,
    db: Session,
) -> Item:
    """
    Create a PENDING item and a PendingConfirmation row linking it to the
    existing item it conflicts with.

    Parameters
    ----------
    item_dict : dict
        Parsed item data (name required; quantity, unit, category optional).
    existing_item_id : int
        ID of the existing ACTIVE item that triggered the duplicate flag.
    triggered_by : int
        User ID of the person who submitted the item.
    db : Session

    Returns
    -------
    Item  (status=PENDING)
    """
    shopping_list = _get_or_create_active_list(db)

    pending_item = Item(
        list_id=shopping_list.id,
        name=item_dict["name"],
        quantity=item_dict.get("quantity"),
        unit=item_dict.get("unit"),
        brand_pref=item_dict.get("brand_hint") or item_dict.get("brand_pref"),
        category=item_dict.get("category"),
        status=ItemStatus.PENDING,
        added_by=triggered_by,
    )
    db.add(pending_item)
    db.flush()  # get pending_item.id

    # Expires in 24 hours by convention
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    confirmation = PendingConfirmation(
        item_id=pending_item.id,
        existing_item_id=existing_item_id,
        triggered_by=triggered_by,
        expires_at=expires_at,
    )
    db.add(confirmation)
    record_event(
        list_id=pending_item.list_id,
        event_type="item.pending_duplicate",
        entity_type="item",
        entity_id=pending_item.id,
        payload={
            "id": pending_item.id,
            "existing_item_id": existing_item_id,
            "name": pending_item.name,
        },
        db=db,
    )
    db.commit()
    db.refresh(pending_item)
    return pending_item


def override_category(item_id: int, category: str, db: Session) -> Item:
    """
    Update an existing item's category.

    Parameters
    ----------
    item_id : int
    category : str
    db : Session

    Returns
    -------
    Item  (updated)

    Raises
    ------
    ValueError if the item is not found.
    """
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise ValueError(f"Item with id={item_id} not found.")

    item.category = category
    item.updated_at = datetime.now(timezone.utc)
    item.version += 1
    db.commit()
    db.refresh(item)
    return item


def update_item(item_id: int, updates: dict, db: Session) -> Item:
    """Update editable item fields and bump version metadata."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise ValueError(f"Item with id={item_id} not found.")

    editable_fields = {"name", "quantity", "unit", "notes"}
    for field in editable_fields:
        if field in updates:
            setattr(item, field, updates[field])

    if "category_id" in updates:
        category_id = updates["category_id"]
        item.category_id = category_id
        if category_id is None:
            item.category = None
        else:
            category = db.query(Category).filter(Category.id == category_id).first()
            if category is None:
                raise ValueError(f"Category with id={category_id} not found.")
            item.category = category.name

    item.updated_at = datetime.now(timezone.utc)
    item.version += 1
    record_event(
        list_id=item.list_id,
        event_type="item.updated",
        entity_type="item",
        entity_id=item.id,
        payload={"id": item.id},
        db=db,
    )
    db.commit()
    db.refresh(item)
    return item


def delete_item(item_id: int, db: Session) -> None:
    """Delete an item by id."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise ValueError(f"Item with id={item_id} not found.")

    list_id = item.list_id
    db.delete(item)
    record_event(
        list_id=list_id,
        event_type="item.deleted",
        entity_type="item",
        entity_id=item_id,
        payload={"id": item_id},
        db=db,
    )
    db.commit()


def toggle_purchased(item_id: int, is_purchased: bool, db: Session) -> Item:
    """Toggle purchased state for an item during an active shopping trip."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise ValueError(f"Item with id={item_id} not found.")

    active_trip = (
        db.query(ShoppingTrip)
        .filter(
            ShoppingTrip.list_id == item.list_id,
            ShoppingTrip.status == TripStatus.ACTIVE,
        )
        .first()
    )
    if active_trip is None:
        raise ValueError("Items can only be checked off during an active shopping trip.")

    item.is_purchased = is_purchased
    item.purchased_at = datetime.now(timezone.utc) if is_purchased else None
    if is_purchased:
        item.new_during_trip = False
    item.updated_at = datetime.now(timezone.utc)
    item.version += 1
    record_event(
        list_id=item.list_id,
        event_type="item.updated",
        entity_type="item",
        entity_id=item.id,
        payload={"id": item.id, "is_purchased": item.is_purchased},
        db=db,
    )

    db.commit()
    db.refresh(item)
    return item
