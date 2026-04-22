"""Realtime event recording helpers."""
import json

from sqlalchemy.orm import Session

from app.models import ListEvent


def record_event(
    *,
    list_id: int | None,
    event_type: str,
    entity_type: str,
    entity_id: int | None,
    payload: dict,
    db: Session,
) -> ListEvent:
    """Persist a realtime event row."""
    event = ListEvent(
        list_id=list_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload_json=json.dumps(payload, sort_keys=True),
    )
    db.add(event)
    db.flush()
    return event


def list_events_after(event_id: int, db: Session) -> list[ListEvent]:
    """Return events strictly after the provided event id."""
    return (
        db.query(ListEvent)
        .filter(ListEvent.id > event_id)
        .order_by(ListEvent.id)
        .all()
    )
