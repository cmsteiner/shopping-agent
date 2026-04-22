"""Conflict resolution helpers."""
from sqlalchemy.orm import Session

from app.models import Item
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
