"""Item service — create and manage shopping list items."""
from sqlalchemy.orm import Session

from app.models import Item, ShoppingList
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
