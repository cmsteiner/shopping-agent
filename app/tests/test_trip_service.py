"""Tests for trip_service."""
import pytest
from sqlalchemy.orm import Session

from app.models import Item, ShoppingList, ShoppingTrip
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus
from app.models.shopping_trip import TripStatus


def _make_list(db: Session, status: ListStatus = ListStatus.ACTIVE) -> ShoppingList:
    sl = ShoppingList(status=status)
    db.add(sl)
    db.flush()
    return sl


def _add_item(
    db: Session,
    list_id: int,
    name: str,
    *,
    status: ItemStatus = ItemStatus.ACTIVE,
    is_purchased: bool = False,
    category: str = "Dairy",
) -> Item:
    item = Item(
        list_id=list_id,
        name=name,
        status=status,
        is_purchased=is_purchased,
        category=category,
    )
    db.add(item)
    db.flush()
    return item


class TestStartTrip:
    def test_starts_trip_for_active_list_with_items(self, db: Session):
        from app.services.trip_service import start_trip

        sl = _make_list(db)
        _add_item(db, sl.id, "Milk")
        db.commit()

        trip = start_trip(db)

        assert trip.id is not None
        assert trip.list_id == sl.id
        assert trip.status == TripStatus.ACTIVE
        assert trip.started_at is not None
        assert trip.version == 1

    def test_rejects_start_when_active_list_is_empty(self, db: Session):
        from app.services.trip_service import start_trip

        _make_list(db)
        db.commit()

        with pytest.raises(ValueError, match="at least one item"):
            start_trip(db)

    def test_ignores_pending_items_when_deciding_if_trip_can_start(self, db: Session):
        from app.services.trip_service import start_trip

        sl = _make_list(db)
        _add_item(db, sl.id, "Milk", status=ItemStatus.PENDING)
        db.commit()

        with pytest.raises(ValueError, match="at least one item"):
            start_trip(db)

    def test_rejects_when_trip_already_active(self, db: Session):
        from app.services.trip_service import start_trip

        sl = _make_list(db)
        _add_item(db, sl.id, "Milk")
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        with pytest.raises(ValueError, match="already in progress"):
            start_trip(db)

    def test_records_trip_started_event(self, db: Session):
        from app.services.trip_service import start_trip
        from app.models import ListEvent

        sl = _make_list(db)
        _add_item(db, sl.id, "Milk")
        db.commit()

        trip = start_trip(db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.list_id == sl.id
        assert event.event_type == "trip.started"
        assert event.entity_type == "trip"
        assert event.entity_id == trip.id


class TestGetActiveTrip:
    def test_returns_active_trip_for_current_list(self, db: Session):
        from app.services.trip_service import get_active_trip

        sl = _make_list(db)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE)
        db.add(trip)
        db.commit()

        found = get_active_trip(db)

        assert found is not None
        assert found.id == trip.id

    def test_returns_none_when_no_active_trip_exists(self, db: Session):
        from app.services.trip_service import get_active_trip

        _make_list(db)
        db.commit()

        assert get_active_trip(db) is None


class TestPrepareFinishTrip:
    def test_returns_unchecked_items_for_active_trip(self, db: Session):
        from app.services.trip_service import prepare_finish_trip

        sl = _make_list(db)
        milk = _add_item(db, sl.id, "Milk", is_purchased=False)
        _add_item(db, sl.id, "Bread", is_purchased=True)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE)
        db.add(trip)
        db.commit()

        active_trip, unchecked_items = prepare_finish_trip(trip.id, db)

        assert active_trip.id == trip.id
        assert [item.id for item in unchecked_items] == [milk.id]

    def test_rejects_missing_trip(self, db: Session):
        from app.services.trip_service import prepare_finish_trip

        with pytest.raises(ValueError, match="not found"):
            prepare_finish_trip(99999, db)

    def test_rejects_non_active_trip(self, db: Session):
        from app.services.trip_service import prepare_finish_trip

        sl = _make_list(db)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.COMPLETED)
        db.add(trip)
        db.commit()

        with pytest.raises(ValueError, match="active"):
            prepare_finish_trip(trip.id, db)


class TestCompleteFinishTrip:
    def test_completes_trip_archives_list_and_creates_new_active_list(self, db: Session):
        from app.services.trip_service import complete_finish_trip

        sl = _make_list(db)
        _add_item(db, sl.id, "Milk", is_purchased=True)
        _add_item(db, sl.id, "Bread", is_purchased=False)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE)
        db.add(trip)
        db.commit()

        completed_trip, archived_list, new_list, carried = complete_finish_trip(
            trip.id,
            [{"item_id": 2, "carry_over": False}],
            db,
        )

        assert completed_trip.status == TripStatus.COMPLETED
        assert completed_trip.completed_at is not None
        assert completed_trip.version == 2

        assert archived_list.id == sl.id
        assert archived_list.status == ListStatus.ARCHIVED
        assert archived_list.archived_at is not None

        assert new_list.id != sl.id
        assert new_list.status == ListStatus.ACTIVE
        assert carried == []

    def test_carries_selected_unchecked_items_to_new_list(self, db: Session):
        from app.services.trip_service import complete_finish_trip

        sl = _make_list(db)
        milk = _add_item(db, sl.id, "Milk", is_purchased=False, category="Dairy")
        bread = _add_item(db, sl.id, "Bread", is_purchased=False, category="Bakery")
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE)
        db.add(trip)
        db.commit()

        completed_trip, archived_list, new_list, carried = complete_finish_trip(
            trip.id,
            [
                {"item_id": milk.id, "carry_over": True},
                {"item_id": bread.id, "carry_over": False},
            ],
            db,
        )

        assert completed_trip.status == TripStatus.COMPLETED
        assert archived_list.status == ListStatus.ARCHIVED
        assert len(carried) == 1
        assert carried[0].name == "Milk"
        assert carried[0].list_id == new_list.id
        assert carried[0].is_purchased is False
        assert carried[0].category == "Dairy"

    def test_rejects_missing_trip(self, db: Session):
        from app.services.trip_service import complete_finish_trip

        with pytest.raises(ValueError, match="not found"):
            complete_finish_trip(99999, [], db)

    def test_rejects_non_active_trip(self, db: Session):
        from app.services.trip_service import complete_finish_trip

        sl = _make_list(db)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.COMPLETED)
        db.add(trip)
        db.commit()

        with pytest.raises(ValueError, match="active"):
            complete_finish_trip(trip.id, [], db)

    def test_records_trip_completed_and_list_replaced_events(self, db: Session):
        from app.services.trip_service import complete_finish_trip
        from app.models import ListEvent

        sl = _make_list(db)
        _add_item(db, sl.id, "Milk", is_purchased=False)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE)
        db.add(trip)
        db.commit()

        complete_finish_trip(trip.id, [], db)

        events = db.query(ListEvent).order_by(ListEvent.id).all()
        event_types = [event.event_type for event in events]
        assert "trip.completed" in event_types
        assert "list.replaced" in event_types
