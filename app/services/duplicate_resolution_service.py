"""Duplicate resolution helpers."""
from datetime import datetime, timezone

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

    existing_item = None
    if confirmation.existing_item_id is not None:
        existing_item = db.query(Item).filter(Item.id == confirmation.existing_item_id).first()

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
        db.delete(confirmation)
        db.commit()
        db.refresh(pending_item)
        return {"decision": decision, "resolved_item": pending_item}

    if decision == "merge":
        if existing_item is None:
            raise ValueError("Existing item not found for merge.")

        existing_quantity = float(existing_item.quantity or 0)
        pending_quantity = float(pending_item.quantity or 0)
        existing_item.quantity = existing_quantity + pending_quantity
        if pending_item.notes and not existing_item.notes:
            existing_item.notes = pending_item.notes
        existing_item.updated_at = datetime.now(timezone.utc)
        existing_item.version += 1
        record_event(
            list_id=existing_item.list_id,
            event_type="item.duplicate_resolved",
            entity_type="item",
            entity_id=existing_item.id,
            payload={"id": existing_item.id, "decision": decision},
            db=db,
        )
        db.delete(confirmation)
        db.delete(pending_item)
        db.commit()
        db.refresh(existing_item)
        return {"decision": decision, "resolved_item": existing_item}

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
