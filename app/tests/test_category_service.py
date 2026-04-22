"""Tests for category service behaviors."""
import pytest
from sqlalchemy.orm import Session

from app.models import Category, Item, ShoppingList
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus


def _make_active_list(db: Session) -> ShoppingList:
    sl = ShoppingList(status=ListStatus.ACTIVE)
    db.add(sl)
    db.flush()
    return sl


class TestCreateCategory:
    def test_creates_category_with_normalized_name_and_version(self, db: Session):
        from app.services.category_service import create_category

        category = create_category("Produce", db)

        assert category.id is not None
        assert category.name == "Produce"
        assert category.normalized_name == "produce"
        assert category.version == 1
        assert category.sort_order > 0

    def test_reuses_existing_category_case_insensitively(self, db: Session):
        from app.services.category_service import create_category

        existing = create_category("Produce", db)
        reused = create_category("produce", db)

        assert reused.id == existing.id
        assert db.query(Category).count() == 1

    def test_records_category_created_event(self, db: Session):
        from app.services.category_service import create_category
        from app.models import ListEvent

        category = create_category("Produce", db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.event_type == "category.created"
        assert event.entity_type == "category"
        assert event.entity_id == category.id


class TestRenameCategory:
    def test_renames_category_and_updates_linked_item_category_text(self, db: Session):
        from app.services.category_service import create_category, rename_category

        category = create_category("Produce", db)
        sl = _make_active_list(db)
        item = Item(
            list_id=sl.id,
            name="Spinach",
            category="Produce",
            category_id=category.id,
            status=ItemStatus.ACTIVE,
        )
        db.add(item)
        db.commit()

        updated = rename_category(category.id, "Fresh Produce", db)
        db.refresh(item)

        assert updated.name == "Fresh Produce"
        assert updated.normalized_name == "fresh produce"
        assert updated.version == 2
        assert item.category == "Fresh Produce"
        assert item.category_id == category.id

    def test_raises_for_missing_category(self, db: Session):
        from app.services.category_service import rename_category

        with pytest.raises(ValueError, match="not found"):
            rename_category(99999, "Fresh Produce", db)

    def test_records_category_updated_event(self, db: Session):
        from app.services.category_service import create_category, rename_category
        from app.models import ListEvent

        category = create_category("Produce", db)

        rename_category(category.id, "Fresh Produce", db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.event_type == "category.updated"
        assert event.entity_type == "category"
        assert event.entity_id == category.id


class TestDeleteCategory:
    def test_deletes_empty_category(self, db: Session):
        from app.services.category_service import create_category, delete_category

        category = create_category("Bakery", db)

        delete_category(category.id, db)

        assert db.query(Category).filter(Category.id == category.id).first() is None

    def test_raises_when_category_still_has_items(self, db: Session):
        from app.services.category_service import create_category, delete_category

        category = create_category("Bakery", db)
        sl = _make_active_list(db)
        db.add(Item(list_id=sl.id, name="Bread", category="Bakery", category_id=category.id))
        db.commit()

        with pytest.raises(ValueError, match="Move all items out of this category"):
            delete_category(category.id, db)

    def test_records_category_deleted_event(self, db: Session):
        from app.services.category_service import create_category, delete_category
        from app.models import ListEvent

        category = create_category("Bakery", db)

        delete_category(category.id, db)

        event = db.query(ListEvent).order_by(ListEvent.id.desc()).first()
        assert event is not None
        assert event.event_type == "category.deleted"
        assert event.entity_type == "category"
        assert event.entity_id == category.id
