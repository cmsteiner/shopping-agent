"""
List lifecycle service.

Handles get_list, send_list, and archive_list operations.
"""
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ShoppingList, Item
from app.models.shopping_list import ListStatus
from app.models.item import ItemStatus


def _get_current_list(db: Session) -> ShoppingList | None:
    """Return the most relevant list (ACTIVE first, then SENT)."""
    # Prefer ACTIVE; fall back to SENT for get_list
    for status in (ListStatus.ACTIVE, ListStatus.SENT):
        sl = db.query(ShoppingList).filter(ShoppingList.status == status).first()
        if sl is not None:
            return sl
    return None


def get_list(db: Session) -> dict:
    """
    Return the current ACTIVE (or SENT) shopping list with items grouped by
    category.  PENDING items are annotated with status="PENDING".

    Returns
    -------
    dict:
        {
          "list_id": int | None,
          "status": str | None,
          "items_by_category": {category: [{"id", "name", "quantity", "unit", "brand_pref", "status"}, ...]}
        }
    """
    shopping_list = _get_current_list(db)
    if shopping_list is None:
        return {"list_id": None, "status": None, "items_by_category": {}}

    items_by_category: dict[str, list[dict]] = defaultdict(list)
    for item in shopping_list.items:
        category = item.category or "Uncategorized"
        items_by_category[category].append({
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "unit": item.unit,
            "brand_pref": item.brand_pref,
            "status": item.status.value if isinstance(item.status, ItemStatus) else str(item.status),
        })

    return {
        "list_id": shopping_list.id,
        "status": shopping_list.status.value,
        "items_by_category": dict(items_by_category),
    }


def send_list(db: Session) -> ShoppingList:
    """
    Transition the current shopping list from ACTIVE → SENT.

    Raises
    ------
    ValueError
        If no ACTIVE list exists.
    """
    shopping_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.ACTIVE)
        .first()
    )
    if shopping_list is None:
        raise ValueError("No ACTIVE list found. Can only send an ACTIVE list.")

    shopping_list.status = ListStatus.SENT
    shopping_list.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(shopping_list)
    return shopping_list


def archive_list(db: Session) -> ShoppingList:
    """
    Transition the current shopping list from SENT → ARCHIVED and create a
    new empty ACTIVE list.

    Raises
    ------
    ValueError
        If no SENT list exists (e.g., list is still ACTIVE).
    """
    shopping_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.SENT)
        .first()
    )
    if shopping_list is None:
        raise ValueError("No SENT list found. Can only archive a SENT list.")

    shopping_list.status = ListStatus.ARCHIVED
    shopping_list.archived_at = datetime.now(timezone.utc)

    # Create a new empty ACTIVE list
    new_list = ShoppingList(status=ListStatus.ACTIVE)
    db.add(new_list)
    db.commit()
    db.refresh(shopping_list)
    return shopping_list
