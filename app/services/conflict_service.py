"""Conflict resolution helpers."""
from sqlalchemy.orm import Session

from app.models import Category, Item
from app.services.category_service import rename_category
from app.services.item_service import update_item


def build_item_conflict(item: Item, client_payload: dict) -> dict:
    """Build a conflict payload for an item version mismatch."""
    return {
        "entity_type": "item",
        "entity_id": item.id,
        "server_version": item.version,
        "client_payload": client_payload,
        "server_payload": {
            "id": item.id,
            "name": item.name,
            "quantity": str(item.quantity) if item.quantity is not None else None,
            "notes": item.notes,
            "category_id": item.category_id,
            "category_name": item.category or "Uncategorized",
            "is_purchased": item.is_purchased,
            "new_during_trip": item.new_during_trip,
            "version": item.version,
            "updated_at": item.updated_at.isoformat().replace("+00:00", "Z") if item.updated_at else None,
        },
    }


def build_category_conflict(category: Category, client_payload: dict) -> dict:
    return {
        "entity_type": "category",
        "entity_id": category.id,
        "server_version": category.version,
        "client_payload": client_payload,
        "server_payload": {
            "id": category.id,
            "name": category.name,
            "sort_order": category.sort_order,
            "version": category.version,
            "updated_at": category.updated_at.isoformat().replace("+00:00", "Z") if category.updated_at else None,
        },
    }


def resolve_item_conflict(
    *,
    item_id: int,
    decision: str,
    server_version: int,
    client_payload: dict,
    db: Session,
) -> Item:
    """Resolve an item conflict using whole-record semantics."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise ValueError(f"Item with id={item_id} not found.")
    if item.version != server_version:
        raise ValueError("Server version does not match the current item version.")

    if decision == "keep_server":
        return item
    if decision == "overwrite_with_client":
        return update_item(item_id, client_payload, db=db)
    raise ValueError(f"Unsupported conflict decision: {decision}")


def resolve_category_conflict(
    *,
    category_id: int,
    decision: str,
    server_version: int,
    client_payload: dict,
    db: Session,
) -> Category:
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise ValueError(f"Category with id={category_id} not found.")
    if category.version != server_version:
        raise ValueError("Server version does not match the current category version.")

    if decision == "keep_server":
        return category
    if decision == "overwrite_with_client":
        return rename_category(category_id, client_payload["name"], db=db)
    raise ValueError(f"Unsupported conflict decision: {decision}")
