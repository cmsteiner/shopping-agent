"""Item service — create and manage shopping list items."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Item, ShoppingList, PendingConfirmation
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus


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

    created = []
    for item_data in items:
        item = Item(
            list_id=list_id,
            name=item_data["name"],
            quantity=item_data.get("quantity"),
            unit=item_data.get("unit"),
            brand_pref=item_data.get("brand_hint") or item_data.get("brand_pref"),
            category=item_data.get("category"),
            status=ItemStatus.ACTIVE,
            added_by=user_id,
        )
        db.add(item)
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
    expires_at = datetime(9999, 12, 31, tzinfo=timezone.utc)
    confirmation = PendingConfirmation(
        item_id=pending_item.id,
        existing_item_id=existing_item_id,
        triggered_by=triggered_by,
        expires_at=expires_at,
    )
    db.add(confirmation)
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
    db.commit()
    db.refresh(item)
    return item
