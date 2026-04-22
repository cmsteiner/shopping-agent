"""Duplicate resolution helpers."""
from sqlalchemy.orm import Session

from app.models import Item, PendingConfirmation
from app.models.item import ItemStatus
from app.services.realtime_service import record_event


def resolve_duplicate(
    *,
    pending_confirmation_id: int,
    decision: str,
    db: Session,
) -> dict:
    """Resolve a pending duplicate confirmation."""
    confirmation = (
        db.query(PendingConfirmation)
        .filter(PendingConfirmation.id == pending_confirmation_id)
        .first()
    )
    if confirmation is None:
        raise ValueError(f"PendingConfirmation with id={pending_confirmation_id} not found.")

    pending_item = db.query(Item).filter(Item.id == confirmation.item_id).first()
    if pending_item is None:
        raise ValueError(f"Pending item with id={confirmation.item_id} not found.")

    if decision == "keep_separate":
        pending_item.status = ItemStatus.ACTIVE
        record_event(
            list_id=pending_item.list_id,
            event_type="item.duplicate_resolved",
            entity_type="item",
            entity_id=pending_item.id,
            payload={"id": pending_item.id, "decision": decision},
            db=db,
        )
        db.commit()
        db.refresh(pending_item)
        return {"decision": decision, "resolved_item": pending_item}

    if decision == "cancel":
        removed_pending_item_id = pending_item.id
        record_event(
            list_id=pending_item.list_id,
            event_type="item.duplicate_resolved",
            entity_type="item",
            entity_id=pending_item.id,
            payload={"id": pending_item.id, "decision": decision},
            db=db,
        )
        db.delete(confirmation)
        db.delete(pending_item)
        db.commit()
        return {"decision": decision, "removed_pending_item_id": removed_pending_item_id}

    raise ValueError(f"Unsupported duplicate decision: {decision}")
