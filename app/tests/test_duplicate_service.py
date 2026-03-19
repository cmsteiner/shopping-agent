"""
Tests for duplicate_service.check_duplicates.

TDD: written before the implementation.
"""
import pytest
from sqlalchemy.orm import Session

from app.models import ShoppingList, Item
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


class TestCheckDuplicates:
    def test_exact_match_flagged(self, db: Session):
        """Exact match 'milk' vs 'milk' → score 100, flagged as duplicate."""
        from app.services.duplicate_service import check_duplicates

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "milk")
        db.commit()

        result = check_duplicates([{"name": "milk"}], db)

        assert result["clear"] == []
        assert len(result["possible_duplicates"]) == 1
        new_item, ex_item, score = result["possible_duplicates"][0]
        assert new_item["name"] == "milk"
        assert ex_item.id == existing.id
        assert score == 100

    def test_substring_match_flagged(self, db: Session):
        """'whole milk' vs existing 'milk' → score >= 85, flagged."""
        from app.services.duplicate_service import check_duplicates

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "milk")
        db.commit()

        result = check_duplicates([{"name": "whole milk"}], db)

        assert result["clear"] == []
        assert len(result["possible_duplicates"]) == 1
        _, _, score = result["possible_duplicates"][0]
        assert score >= 85

    def test_unrelated_items_clear(self, db: Session):
        """'eggs' vs existing 'egg noodles' → score < 85, clear."""
        from app.services.duplicate_service import check_duplicates

        sl = _make_active_list(db)
        _add_item(db, sl.id, "egg noodles")
        db.commit()

        result = check_duplicates([{"name": "eggs"}], db)

        assert len(result["possible_duplicates"]) == 0
        assert len(result["clear"]) == 1
        assert result["clear"][0]["name"] == "eggs"

    def test_empty_list_all_clear(self, db: Session):
        """No existing items → all new items are clear."""
        from app.services.duplicate_service import check_duplicates

        # No active list / items
        result = check_duplicates([{"name": "milk"}, {"name": "eggs"}], db)

        assert result["possible_duplicates"] == []
        assert len(result["clear"]) == 2

    def test_score_exactly_at_threshold_flagged(self, db: Session):
        """A score of exactly 85 should be flagged (>= threshold)."""
        from app.services.duplicate_service import check_duplicates
        from unittest.mock import patch

        sl = _make_active_list(db)
        existing = _add_item(db, sl.id, "banana")
        db.commit()

        # Patch rapidfuzz so we control the exact score
        with patch("app.services.duplicate_service.fuzz.token_set_ratio", return_value=85):
            result = check_duplicates([{"name": "some item"}], db)

        assert len(result["possible_duplicates"]) == 1

    def test_score_below_threshold_clear(self, db: Session):
        """A score of 84 should be clear (< threshold)."""
        from app.services.duplicate_service import check_duplicates
        from unittest.mock import patch

        sl = _make_active_list(db)
        _add_item(db, sl.id, "banana")
        db.commit()

        with patch("app.services.duplicate_service.fuzz.token_set_ratio", return_value=84):
            result = check_duplicates([{"name": "some item"}], db)

        assert result["possible_duplicates"] == []
        assert len(result["clear"]) == 1
