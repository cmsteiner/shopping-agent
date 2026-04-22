"""
Tests for item_service: hold_pending, override_category, update/delete/toggle behaviors.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models import Category, Item, PendingConfirmation, ShoppingList, ShoppingTrip
from app.models.shopping_list import ListStatus
from app.models.item import ItemStatus
from app.models.shopping_trip import TripStatus


def _make_active_list(db: Session) -> ShoppingList:
    sl = ShoppingList(status=ListStatus.ACTIVE)
    db.add(sl)
    db.flush()
    return sl


def _add_item(db: Session, list_id: int, name: str) -> Item:
    item = Item(list_id=list_id, name=name, status=ItemStatus.ACTIVE)
    db.add(item)
    db.flush()
    return item


class TestHoldPending:
    def test_creates_pending_item_in_database(self, db: Session):
        """hold_pending creates an Item with status=PENDING."""
        from app.services.item_service import hold_pending

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "milk")
        db.commit()

        pending = hold_pending(
            item_dict={"name": "whole milk"},
            existing_item_id=existing.id,
            triggered_by=1,
            db=db,
        )

        assert pending.id is not None
        assert pending.name == "whole milk"
        assert pending.status == ItemStatus.PENDING

        # Verify it's in the DB
        in_db = db.query(Item).filter(Item.id == pending.id).first()
        assert in_db is not None
        assert in_db.status == ItemStatus.PENDING

    def test_creates_pending_confirmation_row_linked_to_item(self, db: Session):
        """hold_pending creates a PendingConfirmation linked to the new item."""
        from app.services.item_service import hold_pending

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "eggs")
        db.commit()

        pending = hold_pending(
            item_dict={"name": "brown eggs"},
            existing_item_id=existing.id,
            triggered_by=1,
            db=db,
        )

        confirmation = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.item_id == pending.id)
            .first()
        )
        assert confirmation is not None
        assert confirmation.item_id == pending.id
        assert confirmation.existing_item_id == existing.id

    def test_expires_at_is_within_25_hours(self, db: Session):
        """hold_pending sets a real expires_at within 25 hours (not a far-future sentinel)."""
        from app.services.item_service import hold_pending

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "butter")
        db.commit()

        before = datetime.now(timezone.utc)
        pending = hold_pending(
            item_dict={"name": "unsalted butter"},
            existing_item_id=existing.id,
            triggered_by=1,
            db=db,
        )
        after = datetime.now(timezone.utc)

        confirmation = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.item_id == pending.id)
            .first()
        )
        assert confirmation is not None

        expires = confirmation.expires_at
        # Ensure the stored value is timezone-aware
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        # Must expire within 25 hours from now (not year 9999)
        assert expires <= after + timedelta(hours=25)
        # Must expire at least 23 hours from now (close to the intended 24h window)
        assert expires >= before + timedelta(hours=23)

    def test_records_item_pending_duplicate_event(self, db: Session):
        from app.models import ListEvent
        from app.services.item_service import hold_pending

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "milk")
        db.commit()

        pending = hold_pending(
            item_dict={"name": "whole milk"},
            existing_item_id=existing.id,
            triggered_by=1,
            db=db,
        )

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.pending_duplicate"
        assert event.entity_id == pending.id


class TestOverrideCategory:
    def test_updates_item_category(self, db: Session):
        """override_category changes the item's category and persists it."""
        from app.services.item_service import override_category

        sl = _make_active_list(db)
        item = _add_item(db, sl.id, "spinach")
        item.category = "Uncategorized"
        db.commit()

        updated = override_category(item_id=item.id, category="Produce", db=db)

        assert updated.id == item.id
        assert updated.category == "Produce"

        # Verify persistence
        in_db = db.query(Item).filter(Item.id == item.id).first()
        assert in_db.category == "Produce"

    def test_raises_value_error_for_missing_item_id(self, db: Session):
        """override_category raises ValueError if the item ID does not exist."""
        from app.services.item_service import override_category

        with pytest.raises(ValueError, match="not found"):
            override_category(item_id=99999, category="Produce", db=db)


class TestUpdateItem:
    def test_updates_editable_fields_and_increments_version(self, db: Session):
        from app.services.item_service import update_item

        sl = _make_active_list(db)
        category = Category(name="Produce", normalized_name="produce", sort_order=10)
        db.add(category)
        db.flush()
        item = Item(list_id=sl.id, name="Apple", quantity=1, category="Produce", category_id=category.id)
        db.add(item)
        db.commit()

        updated = update_item(
            item.id,
            {
                "name": "Apples",
                "quantity": 2,
                "notes": "Honeycrisp",
            },
            db=db,
        )

        assert updated.name == "Apples"
        assert float(updated.quantity) == 2.0
        assert updated.notes == "Honeycrisp"
        assert updated.version == 2
        assert updated.updated_at >= updated.created_at

    def test_updates_category_text_when_category_id_changes(self, db: Session):
        from app.services.item_service import update_item

        sl = _make_active_list(db)
        old_category = Category(name="Produce", normalized_name="produce", sort_order=10)
        new_category = Category(name="Bakery", normalized_name="bakery", sort_order=20)
        db.add_all([old_category, new_category])
        db.flush()
        item = Item(list_id=sl.id, name="Bread", category="Produce", category_id=old_category.id)
        db.add(item)
        db.commit()

        updated = update_item(item.id, {"category_id": new_category.id}, db=db)

        assert updated.category_id == new_category.id
        assert updated.category == "Bakery"

    def test_raises_for_missing_item(self, db: Session):
        from app.services.item_service import update_item

        with pytest.raises(ValueError, match="not found"):
            update_item(99999, {"name": "Missing"}, db=db)

    def test_records_item_updated_event(self, db: Session):
        from app.services.item_service import update_item
        from app.models import ListEvent

        sl = _make_active_list(db)
        item = _add_item(db, sl.id, "Apple")
        db.commit()

        update_item(item.id, {"name": "Apples"}, db=db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.updated"
        assert event.entity_type == "item"
        assert event.entity_id == item.id


class TestAddItems:
    def test_defaults_quantity_and_marks_new_during_active_trip(self, db: Session):
        from app.services.item_service import add_items

        sl = _make_active_list(db)
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        [created] = add_items(
            [{"name": "Milk"}],
            list_id=sl.id,
            user_id=1,
            db=db,
        )

        assert float(created.quantity) == 1.0
        assert created.new_during_trip is True

    def test_records_item_created_event(self, db: Session):
        from app.services.item_service import add_items
        from app.models import ListEvent

        sl = _make_active_list(db)

        [created] = add_items(
            [{"name": "Milk", "notes": "2%"}],
            list_id=sl.id,
            user_id=1,
            db=db,
        )

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.created"
        assert event.entity_type == "item"
        assert event.entity_id == created.id
        assert '"name": "Milk"' in event.payload_json


class TestDeleteItem:
    def test_deletes_item(self, db: Session):
        from app.services.item_service import delete_item

        sl = _make_active_list(db)
        item = _add_item(db, sl.id, "Milk")
        db.commit()

        delete_item(item.id, db=db)

        assert db.query(Item).filter(Item.id == item.id).first() is None

    def test_raises_for_missing_item(self, db: Session):
        from app.services.item_service import delete_item

        with pytest.raises(ValueError, match="not found"):
            delete_item(99999, db=db)

    def test_records_item_deleted_event(self, db: Session):
        from app.services.item_service import delete_item
        from app.models import ListEvent

        sl = _make_active_list(db)
        item = _add_item(db, sl.id, "Milk")
        db.commit()

        delete_item(item.id, db=db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.deleted"
        assert event.entity_type == "item"
        assert event.entity_id == item.id


class TestTogglePurchased:
    def test_marks_item_purchased_during_active_trip(self, db: Session):
        from app.services.item_service import toggle_purchased

        sl = _make_active_list(db)
        item = Item(list_id=sl.id, name="Milk", new_during_trip=True)
        db.add(item)
        db.flush()
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        updated = toggle_purchased(item.id, True, db=db)

        assert updated.is_purchased is True
        assert updated.purchased_at is not None
        assert updated.new_during_trip is False
        assert updated.version == 2

    def test_unchecks_item_during_active_trip(self, db: Session):
        from app.services.item_service import toggle_purchased

        sl = _make_active_list(db)
        item = Item(list_id=sl.id, name="Milk", is_purchased=True, purchased_at=datetime.now(timezone.utc))
        db.add(item)
        db.flush()
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        updated = toggle_purchased(item.id, False, db=db)

        assert updated.is_purchased is False
        assert updated.purchased_at is None
        assert updated.version == 2

    def test_raises_when_no_active_trip(self, db: Session):
        from app.services.item_service import toggle_purchased

        sl = _make_active_list(db)
        item = _add_item(db, sl.id, "Milk")
        db.commit()

        with pytest.raises(ValueError, match="active shopping trip"):
            toggle_purchased(item.id, True, db=db)

    def test_records_item_updated_event(self, db: Session):
        from app.services.item_service import toggle_purchased
        from app.models import ListEvent

        sl = _make_active_list(db)
        item = Item(list_id=sl.id, name="Milk")
        db.add(item)
        db.flush()
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        toggle_purchased(item.id, True, db=db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.updated"
