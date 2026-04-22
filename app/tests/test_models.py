"""
Tests for ORM models: User, ShoppingList, Item, BrandPreference, Message, PendingConfirmation.
Write these tests FIRST (red), then implement the models (green).
"""
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    BrandPreference,
    Category,
    Item,
    ListEvent,
    Message,
    PendingConfirmation,
    ShoppingList,
    ShoppingTrip,
    User,
)
from app.models.shopping_list import ListStatus
from app.models.item import ItemStatus
from app.models.message import MessageDirection
from app.models.shopping_trip import TripStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(session: Session, name: str, phone: str) -> User:
    u = User(name=name, phone_number=phone)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def make_list(session: Session, status: ListStatus = ListStatus.ACTIVE) -> ShoppingList:
    sl = ShoppingList(status=status)
    session.add(sl)
    session.commit()
    session.refresh(sl)
    return sl


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class TestUser:
    def test_create_user(self, db: Session):
        u = make_user(db, "Alice", "+10000000001")
        assert u.id is not None
        assert u.name == "Alice"
        assert u.phone_number == "+10000000001"

    def test_phone_number_unique(self, db: Session):
        make_user(db, "Alice", "+10000000002")
        with pytest.raises(Exception):
            make_user(db, "Alice2", "+10000000002")

    def test_user_repr_contains_name(self, db: Session):
        u = make_user(db, "Bob", "+10000000003")
        assert "Bob" in repr(u)


# ---------------------------------------------------------------------------
# ShoppingList
# ---------------------------------------------------------------------------

class TestShoppingList:
    def test_create_list_defaults_to_active(self, db: Session):
        sl = ShoppingList()
        db.add(sl)
        db.commit()
        db.refresh(sl)
        assert sl.status == ListStatus.ACTIVE
        assert sl.created_at is not None

    def test_list_status_enum_values(self, db: Session):
        assert ListStatus.ACTIVE.value == "ACTIVE"
        assert ListStatus.SENT.value == "SENT"
        assert ListStatus.ARCHIVED.value == "ARCHIVED"

    def test_list_sent_at_nullable(self, db: Session):
        sl = make_list(db, ListStatus.ACTIVE)
        assert sl.sent_at is None

    def test_list_archived_at_nullable(self, db: Session):
        sl = make_list(db, ListStatus.ACTIVE)
        assert sl.archived_at is None

    def test_list_status_can_be_updated(self, db: Session):
        sl = make_list(db, ListStatus.ACTIVE)
        sl.status = ListStatus.SENT
        sl.sent_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sl)
        assert sl.status == ListStatus.SENT
        assert sl.sent_at is not None

    def test_list_defaults_version_to_one(self, db: Session):
        sl = make_list(db)
        assert sl.version == 1


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------

class TestItem:
    def test_create_item(self, db: Session):
        user = make_user(db, "Chris", "+15559990001")
        sl = make_list(db)
        item = Item(
            list_id=sl.id,
            name="Milk",
            quantity=2,
            unit="gallons",
            brand_pref="Organic Valley",
            category="DAIRY",
            status=ItemStatus.ACTIVE,
            added_by=user.id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.id is not None
        assert item.name == "Milk"
        assert item.status == ItemStatus.ACTIVE
        assert item.list_id == sl.id
        assert item.added_by == user.id

    def test_item_status_enum_values(self, db: Session):
        assert ItemStatus.ACTIVE.value == "ACTIVE"
        assert ItemStatus.PENDING.value == "PENDING"

    def test_item_fk_to_list(self, db: Session):
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Eggs")
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.list_id == sl.id

    def test_item_optional_fields_nullable(self, db: Session):
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Bread")
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.quantity is None
        assert item.unit is None
        assert item.brand_pref is None
        assert item.category is None
        assert item.category_id is None
        assert item.notes is None
        assert item.added_by is None

    def test_item_default_status_is_active(self, db: Session):
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Butter")
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.status == ItemStatus.ACTIVE

    def test_item_created_at_set(self, db: Session):
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Cheese")
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.created_at is not None

    def test_item_web_fields_default_correctly(self, db: Session):
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Lettuce")
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.is_purchased is False
        assert item.purchased_at is None
        assert item.new_during_trip is False
        assert item.updated_at is not None
        assert item.version == 1


class TestCategory:
    def test_create_category(self, db: Session):
        category = Category(name="Produce", normalized_name="produce", sort_order=10)
        db.add(category)
        db.commit()
        db.refresh(category)
        assert category.id is not None
        assert category.name == "Produce"
        assert category.normalized_name == "produce"
        assert category.sort_order == 10
        assert category.version == 1

    def test_category_normalized_name_unique(self, db: Session):
        db.add(Category(name="Produce", normalized_name="produce", sort_order=10))
        db.commit()
        db.add(Category(name="PRODUCE", normalized_name="produce", sort_order=20))
        with pytest.raises(Exception):
            db.commit()


class TestShoppingTrip:
    def test_create_trip_defaults_active(self, db: Session):
        sl = make_list(db)
        trip = ShoppingTrip(list_id=sl.id)
        db.add(trip)
        db.commit()
        db.refresh(trip)
        assert trip.status == TripStatus.ACTIVE
        assert trip.started_at is not None
        assert trip.completed_at is None
        assert trip.version == 1

    def test_trip_status_enum_values(self, db: Session):
        assert TripStatus.ACTIVE.value == "ACTIVE"
        assert TripStatus.COMPLETED.value == "COMPLETED"


class TestListEvent:
    def test_create_list_event(self, db: Session):
        sl = make_list(db)
        event = ListEvent(
            list_id=sl.id,
            event_type="item.created",
            entity_type="item",
            entity_id=1,
            payload_json='{"id": 1}',
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        assert event.id is not None
        assert event.list_id == sl.id
        assert event.event_type == "item.created"
        assert event.entity_type == "item"
        assert event.payload_json == '{"id": 1}'
        assert event.created_at is not None


# ---------------------------------------------------------------------------
# BrandPreference
# ---------------------------------------------------------------------------

class TestBrandPreference:
    def test_create_brand_preference(self, db: Session):
        user = make_user(db, "Donna", "+15550000002")
        bp = BrandPreference(
            item_name="milk",
            brand="Organic Valley",
            set_by=user.id,
        )
        db.add(bp)
        db.commit()
        db.refresh(bp)
        assert bp.id is not None
        assert bp.item_name == "milk"
        assert bp.brand == "Organic Valley"
        assert bp.set_by == user.id
        assert bp.updated_at is not None

    def test_brand_preference_set_by_fk(self, db: Session):
        user = make_user(db, "Chris2", "+15550000003")
        bp = BrandPreference(item_name="eggs", brand="Vital Farms", set_by=user.id)
        db.add(bp)
        db.commit()
        db.refresh(bp)
        assert bp.set_by == user.id


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class TestMessage:
    def test_create_inbound_message(self, db: Session):
        user = make_user(db, "Chris3", "+15550000004")
        msg = Message(
            user_id=user.id,
            direction=MessageDirection.INBOUND,
            body="Add milk and eggs",
            twilio_sid="SMabc123",
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        assert msg.id is not None
        assert msg.direction == MessageDirection.INBOUND
        assert msg.body == "Add milk and eggs"
        assert msg.twilio_sid == "SMabc123"
        assert msg.created_at is not None

    def test_message_direction_enum_values(self, db: Session):
        assert MessageDirection.INBOUND.value == "INBOUND"
        assert MessageDirection.OUTBOUND.value == "OUTBOUND"

    def test_twilio_sid_unique(self, db: Session):
        user = make_user(db, "Donna2", "+15550000005")
        msg1 = Message(user_id=user.id, direction=MessageDirection.INBOUND, body="hi", twilio_sid="SMdup")
        msg2 = Message(user_id=user.id, direction=MessageDirection.OUTBOUND, body="bye", twilio_sid="SMdup")
        db.add(msg1)
        db.commit()
        db.add(msg2)
        with pytest.raises(Exception):
            db.commit()

    def test_twilio_sid_nullable(self, db: Session):
        user = make_user(db, "Chris4", "+15550000006")
        msg = Message(user_id=user.id, direction=MessageDirection.OUTBOUND, body="Hello")
        db.add(msg)
        db.commit()
        db.refresh(msg)
        assert msg.twilio_sid is None


# ---------------------------------------------------------------------------
# PendingConfirmation
# ---------------------------------------------------------------------------

class TestPendingConfirmation:
    def test_create_pending_confirmation(self, db: Session):
        user = make_user(db, "Chris5", "+15550000007")
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Apples", status=ItemStatus.PENDING)
        existing = Item(list_id=sl.id, name="Apple", status=ItemStatus.ACTIVE)
        db.add_all([item, existing])
        db.commit()
        db.refresh(item)
        db.refresh(existing)

        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        pc = PendingConfirmation(
            item_id=item.id,
            existing_item_id=existing.id,
            triggered_by=user.id,
            expires_at=expires,
        )
        db.add(pc)
        db.commit()
        db.refresh(pc)

        assert pc.id is not None
        assert pc.item_id == item.id
        assert pc.existing_item_id == existing.id
        assert pc.triggered_by == user.id
        assert pc.expires_at is not None
        assert pc.created_at is not None

    def test_existing_item_id_nullable(self, db: Session):
        user = make_user(db, "Donna3", "+15550000008")
        sl = make_list(db)
        item = Item(list_id=sl.id, name="Yogurt", status=ItemStatus.PENDING)
        db.add(item)
        db.commit()
        db.refresh(item)

        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        pc = PendingConfirmation(
            item_id=item.id,
            triggered_by=user.id,
            expires_at=expires,
        )
        db.add(pc)
        db.commit()
        db.refresh(pc)
        assert pc.existing_item_id is None


# ---------------------------------------------------------------------------
# Invariant: only one ACTIVE or SENT list at a time
#
# The DB schema does NOT enforce this invariant — there is no unique index or
# check constraint preventing multiple ACTIVE lists at the SQL level.
# Enforcement is entirely at the application layer (list_service.py), which
# will be tested in Phase 3.
# ---------------------------------------------------------------------------

class TestListInvariant:
    def test_db_does_not_enforce_single_active_list(self, db: Session):
        """
        Documents that the database does NOT prevent inserting two ACTIVE lists.
        The single-active-list invariant is enforced at the application layer
        (list_service.py), not by a DB constraint. This test intentionally
        inserts two ACTIVE lists to confirm no IntegrityError is raised.
        Application-layer enforcement will be tested in Phase 3.
        """
        sl1 = ShoppingList(status=ListStatus.ACTIVE)
        sl2 = ShoppingList(status=ListStatus.ACTIVE)
        db.add_all([sl1, sl2])
        db.commit()  # must NOT raise — DB has no constraint here

        active_count = db.query(ShoppingList).filter(
            ShoppingList.status == ListStatus.ACTIVE
        ).count()
        assert active_count >= 2  # gap acknowledged; application layer must guard this

    def test_can_have_multiple_archived_lists(self, db: Session):
        sl1 = ShoppingList(status=ListStatus.ARCHIVED)
        sl2 = ShoppingList(status=ListStatus.ARCHIVED)
        db.add_all([sl1, sl2])
        db.commit()
        archived_count = db.query(ShoppingList).filter(
            ShoppingList.status == ListStatus.ARCHIVED
        ).count()
        assert archived_count >= 2
