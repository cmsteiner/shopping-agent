"""
Tests for item_service: hold_pending, override_category.
"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from app.models import Item, ShoppingList, PendingConfirmation
from app.models.shopping_list import ListStatus
from app.models.item import ItemStatus


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
