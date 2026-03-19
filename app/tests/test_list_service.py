"""
Tests for list_service: get_list, send_list, archive_list.

TDD: written before the implementation.
"""
import pytest
from sqlalchemy.orm import Session

from app.models import ShoppingList, Item, User
from app.models.shopping_list import ListStatus
from app.models.item import ItemStatus


def _make_list(db: Session, status: ListStatus = ListStatus.ACTIVE) -> ShoppingList:
    sl = ShoppingList(status=status)
    db.add(sl)
    db.flush()
    return sl


def _add_item(db: Session, list_id: int, name: str, category: str = "Dairy",
              status: ItemStatus = ItemStatus.ACTIVE) -> Item:
    item = Item(list_id=list_id, name=name, category=category, status=status)
    db.add(item)
    db.flush()
    return item


class TestGetList:
    def test_groups_items_by_category(self, db: Session):
        """get_list returns items grouped by category."""
        from app.services.list_service import get_list

        sl = _make_list(db)
        _add_item(db, sl.id, "milk", category="Dairy")
        _add_item(db, sl.id, "cheddar", category="Dairy")
        _add_item(db, sl.id, "apples", category="Produce")
        db.commit()

        result = get_list(db)

        assert "Dairy" in result["items_by_category"]
        assert "Produce" in result["items_by_category"]
        assert len(result["items_by_category"]["Dairy"]) == 2
        assert len(result["items_by_category"]["Produce"]) == 1

    def test_pending_items_annotated_distinctly(self, db: Session):
        """PENDING items are annotated differently from ACTIVE items."""
        from app.services.list_service import get_list

        sl = _make_list(db)
        _add_item(db, sl.id, "milk", category="Dairy", status=ItemStatus.ACTIVE)
        _add_item(db, sl.id, "eggs", category="Dairy", status=ItemStatus.PENDING)
        db.commit()

        result = get_list(db)

        dairy_items = result["items_by_category"]["Dairy"]
        statuses = {item["name"]: item["status"] for item in dairy_items}
        assert statuses["milk"] == "ACTIVE"
        assert statuses["eggs"] == "PENDING"


class TestSendList:
    def test_transitions_active_to_sent(self, db: Session):
        """send_list transitions ACTIVE → SENT and records sent_at."""
        from app.services.list_service import send_list

        sl = _make_list(db)
        db.commit()

        updated = send_list(db)

        assert updated.status == ListStatus.SENT
        assert updated.sent_at is not None

    def test_send_list_rejects_non_active(self, db: Session):
        """send_list raises ValueError if list is not ACTIVE."""
        from app.services.list_service import send_list

        sl = _make_list(db, status=ListStatus.SENT)
        db.commit()

        with pytest.raises(ValueError, match="ACTIVE"):
            send_list(db)

    def test_send_list_rejects_archived(self, db: Session):
        """send_list raises ValueError if list is ARCHIVED."""
        from app.services.list_service import send_list

        sl = _make_list(db, status=ListStatus.ARCHIVED)
        db.commit()

        with pytest.raises(ValueError):
            send_list(db)


class TestArchiveList:
    def test_transitions_sent_to_archived(self, db: Session):
        """archive_list transitions SENT → ARCHIVED, creates new ACTIVE list."""
        from app.services.list_service import archive_list

        sl = _make_list(db, status=ListStatus.SENT)
        db.commit()

        archived = archive_list(db)

        assert archived.status == ListStatus.ARCHIVED
        assert archived.archived_at is not None

        # A new ACTIVE list must have been created
        new_list = (
            db.query(ShoppingList)
            .filter(ShoppingList.status == ListStatus.ACTIVE)
            .first()
        )
        assert new_list is not None
        assert new_list.id != archived.id

    def test_archive_list_rejects_active(self, db: Session):
        """archive_list raises ValueError if list is ACTIVE (not SENT)."""
        from app.services.list_service import archive_list

        sl = _make_list(db, status=ListStatus.ACTIVE)
        db.commit()

        with pytest.raises(ValueError, match="SENT"):
            archive_list(db)

    def test_invalid_transition_active_to_archived_rejected(self, db: Session):
        """Direct ACTIVE → ARCHIVED transition is rejected."""
        from app.services.list_service import archive_list

        sl = _make_list(db, status=ListStatus.ACTIVE)
        db.commit()

        with pytest.raises(ValueError):
            archive_list(db)
