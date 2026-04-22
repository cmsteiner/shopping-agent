"""Tests for realtime event recording."""
from sqlalchemy.orm import Session

from app.models import ListEvent, ShoppingList
from app.models.shopping_list import ListStatus


def _make_list(db: Session, status: ListStatus = ListStatus.ACTIVE) -> ShoppingList:
    sl = ShoppingList(status=status)
    db.add(sl)
    db.flush()
    return sl


class TestRecordEvent:
    def test_records_event_row(self, db: Session):
        from app.services.realtime_service import record_event

        sl = _make_list(db)
        event = record_event(
            list_id=sl.id,
            event_type="item.created",
            entity_type="item",
            entity_id=123,
            payload={"id": 123, "name": "Milk"},
            db=db,
        )

        assert event.id is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.created"
        assert event.entity_type == "item"
        assert event.entity_id == 123
        assert '"name": "Milk"' in event.payload_json

    def test_lists_events_after_id(self, db: Session):
        from app.services.realtime_service import list_events_after

        sl = _make_list(db)
        db.add_all(
            [
                ListEvent(list_id=sl.id, event_type="item.created", entity_type="item", entity_id=1, payload_json='{"id":1}'),
                ListEvent(list_id=sl.id, event_type="item.updated", entity_type="item", entity_id=1, payload_json='{"id":1}'),
            ]
        )
        db.commit()

        first = db.query(ListEvent).order_by(ListEvent.id).first()
        events = list_events_after(first.id, db)

        assert len(events) == 1
        assert events[0].event_type == "item.updated"
