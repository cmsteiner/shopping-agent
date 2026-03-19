"""
Tests for SMS formatting utilities.

Tests cover:
- format_list: produces correct SMS text from list_data dict
- split_sms: splits at category boundaries when over max_chars
- normalize_category: maps raw strings to canonical categories
"""
import pytest
from unittest.mock import patch
from datetime import date


# ---------------------------------------------------------------------------
# Helpers to build list_data dicts
# ---------------------------------------------------------------------------

def _make_list_data(items_by_category: dict) -> dict:
    """Build a minimal list_data dict as returned by list_service.get_list."""
    return {
        "list_id": 1,
        "status": "ACTIVE",
        "items_by_category": items_by_category,
    }


def _item(name, quantity=None, brand_pref=None, status="ACTIVE"):
    return {
        "id": 1,
        "name": name,
        "quantity": quantity,
        "unit": None,
        "brand_pref": brand_pref,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Tests for format_list
# ---------------------------------------------------------------------------

class TestFormatList:
    """Tests for app.utils.formatting.format_list."""

    def _format(self, items_by_category):
        from app.utils.formatting import format_list
        list_data = _make_list_data(items_by_category)
        return format_list(list_data)

    def test_header_uses_today_date(self):
        """Header line is SHOPPING LIST - {month} {day} using today's date."""
        from app.utils.formatting import format_list
        # Patch date so we get a predictable result
        fixed_date = date(2026, 3, 15)
        with patch("app.utils.formatting.date") as mock_date:
            mock_date.today.return_value = fixed_date
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            result = format_list(_make_list_data({"DAIRY": [_item("Milk")]}))
        assert result.startswith("SHOPPING LIST - Mar 15")

    def test_category_header_in_all_caps(self):
        """Category names appear in ALL CAPS."""
        result = self._format({"dairy": [_item("Milk")]})
        lines = result.splitlines()
        # Find the category line (after the blank line after the header)
        category_lines = [l for l in lines if l and not l.startswith("SHOPPING LIST") and not l.startswith("-") and not l.startswith("*") and not l.startswith("Reply")]
        assert any(l == "DAIRY" for l in category_lines)

    def test_item_no_quantity_no_brand(self):
        """Plain item renders as '- Name'."""
        result = self._format({"PRODUCE": [_item("Bananas")]})
        assert "- Bananas" in result

    def test_item_with_quantity(self):
        """Item with quantity renders as '- Name x{qty}'."""
        result = self._format({"DAIRY": [_item("Milk", quantity=2)]})
        assert "- Milk x2" in result

    def test_item_with_brand(self):
        """Item with brand renders as '- Name (Brand)'."""
        result = self._format({"DAIRY": [_item("Milk", brand_pref="Organic Valley")]})
        assert "- Milk (Organic Valley)" in result

    def test_item_with_quantity_and_brand(self):
        """Item with both qty and brand renders as '- Name x{qty} (Brand)'."""
        result = self._format({"DAIRY": [_item("Milk", quantity=2, brand_pref="Organic Valley")]})
        assert "- Milk x2 (Organic Valley)" in result

    def test_pending_item_gets_asterisk(self):
        """PENDING items get a trailing '*'."""
        result = self._format({"DAIRY": [_item("Eggs", status="PENDING")]})
        assert "- Eggs*" in result

    def test_active_item_no_asterisk(self):
        """ACTIVE items do NOT get '*'."""
        result = self._format({"DAIRY": [_item("Milk", status="ACTIVE")]})
        assert "- Milk" in result
        assert "- Milk*" not in result

    def test_footer_present(self):
        """Footer lines appear at the end of the formatted text."""
        result = self._format({"DAIRY": [_item("Milk")]})
        assert "* = pending confirmation" in result
        assert "Reply DONE when finished." in result

    def test_footer_at_end(self):
        """Footer is the last content in the formatted text."""
        result = self._format({"DAIRY": [_item("Milk")]})
        assert result.strip().endswith("Reply DONE when finished.")

    def test_blank_line_after_category_block(self):
        """There is a blank line between category blocks."""
        result = self._format({
            "DAIRY": [_item("Milk")],
            "PRODUCE": [_item("Bananas")],
        })
        # There should be at least one blank line (two consecutive newlines) in the body
        assert "\n\n" in result

    def test_categories_sorted_by_canonical_order(self):
        """Categories appear in canonical order: PRODUCE before DAIRY."""
        result = self._format({
            "DAIRY": [_item("Milk")],
            "PRODUCE": [_item("Bananas")],
        })
        produce_pos = result.index("PRODUCE")
        dairy_pos = result.index("DAIRY")
        assert produce_pos < dairy_pos

    def test_quantity_is_integer_when_whole_number(self):
        """Quantity of 2.0 renders as 'x2' (no decimal)."""
        result = self._format({"DAIRY": [_item("Milk", quantity=2.0)]})
        assert "x2" in result
        assert "x2.0" not in result

    def test_pending_with_brand_and_quantity(self):
        """PENDING item with qty and brand: '- Name x2 (Brand)*'."""
        result = self._format({
            "DAIRY": [_item("Milk", quantity=2, brand_pref="Organic Valley", status="PENDING")]
        })
        assert "- Milk x2 (Organic Valley)*" in result


# ---------------------------------------------------------------------------
# Tests for split_sms
# ---------------------------------------------------------------------------

class TestSplitSms:
    """Tests for app.utils.formatting.split_sms."""

    def _split(self, text, max_chars=1500):
        from app.utils.formatting import split_sms
        return split_sms(text, max_chars=max_chars)

    def test_short_text_returns_single_chunk_no_prefix(self):
        """Text under max_chars returns as a single-element list with no part prefix."""
        text = "SHOPPING LIST - Mar 15\n\nDAIRY\n- Milk\n\n* = pending confirmation\nReply DONE when finished."
        result = self._split(text, max_chars=1500)
        assert len(result) == 1
        assert result[0] == text

    def test_single_chunk_has_no_part_number(self):
        """A single-chunk result does not start with '(1/1)'."""
        text = "Short text"
        result = self._split(text, max_chars=1500)
        assert not result[0].startswith("(")

    def test_long_text_splits_into_multiple_chunks(self):
        """Text over max_chars splits into multiple chunks."""
        # Build a text that will definitely be over a small max_chars
        lines = ["SHOPPING LIST - Mar 15", ""]
        for i in range(20):
            lines.append(f"CATEGORY{i}")
            lines.append(f"- Item {i} with a relatively long name here")
            lines.append("")
        lines.append("* = pending confirmation\nReply DONE when finished.")
        text = "\n".join(lines)
        result = self._split(text, max_chars=200)
        assert len(result) > 1

    def test_multi_chunk_parts_have_prefix(self):
        """Each chunk of a multi-chunk split is prefixed with (N/M)."""
        lines = ["SHOPPING LIST - Mar 15", ""]
        for i in range(10):
            lines.append(f"CATEGORY{i}")
            lines.append(f"- Item {i}")
            lines.append("")
        lines.append("* = pending confirmation\nReply DONE when finished.")
        text = "\n".join(lines)
        result = self._split(text, max_chars=100)
        for idx, chunk in enumerate(result):
            assert chunk.startswith(f"({idx + 1}/{len(result)})")

    def test_footer_only_on_last_chunk(self):
        """Footer appears only on the last chunk."""
        lines = ["SHOPPING LIST - Mar 15", ""]
        for i in range(10):
            lines.append(f"CATEGORY{i}")
            lines.append(f"- Item {i}")
            lines.append("")
        lines.append("* = pending confirmation\nReply DONE when finished.")
        text = "\n".join(lines)
        result = self._split(text, max_chars=100)
        assert len(result) > 1
        # Only last chunk has the footer
        assert "Reply DONE when finished." in result[-1]
        for chunk in result[:-1]:
            assert "Reply DONE when finished." not in chunk

    def test_each_chunk_within_max_chars(self):
        """Every chunk is within max_chars."""
        lines = ["SHOPPING LIST - Mar 15", ""]
        for i in range(15):
            lines.append(f"CATEGORY{i}")
            lines.append(f"- Item {i}")
            lines.append("")
        lines.append("* = pending confirmation\nReply DONE when finished.")
        text = "\n".join(lines)
        max_chars = 150
        result = self._split(text, max_chars=max_chars)
        for chunk in result:
            assert len(chunk) <= max_chars, f"Chunk too long ({len(chunk)} > {max_chars}): {chunk!r}"


# ---------------------------------------------------------------------------
# Tests for normalize_category
# ---------------------------------------------------------------------------

class TestNormalizeCategory:
    """Tests for app.utils.category.normalize_category."""

    def _normalize(self, raw):
        from app.utils.category import normalize_category
        return normalize_category(raw)

    def test_exact_canonical_match(self):
        """Exact canonical name returns itself."""
        assert self._normalize("PRODUCE") == "PRODUCE"
        assert self._normalize("DAIRY") == "DAIRY"

    def test_case_insensitive_match(self):
        """Lowercase or mixed-case input matches the canonical name."""
        assert self._normalize("dairy") == "DAIRY"
        assert self._normalize("Produce") == "PRODUCE"
        assert self._normalize("meat") == "MEAT"

    def test_unknown_falls_back_to_other(self):
        """Unknown categories fall back to 'OTHER'."""
        assert self._normalize("Exotic Imports") == "OTHER"
        assert self._normalize("random") == "OTHER"

    def test_all_canonical_categories_recognized(self):
        """Every canonical category maps to itself."""
        from app.utils.category import CANONICAL_CATEGORIES
        for cat in CANONICAL_CATEGORIES:
            assert self._normalize(cat) == cat

    def test_empty_string_falls_back_to_other(self):
        """Empty string returns 'OTHER'."""
        assert self._normalize("") == "OTHER"


# ---------------------------------------------------------------------------
# Tests for item_service brand auto-apply
# ---------------------------------------------------------------------------

class TestAddItemsBrandAutoApply:
    """Tests that add_items auto-applies brand preferences when no brand given."""

    def test_auto_applies_brand_when_preference_exists(self, db):
        """If a brand preference exists for the item name and no brand given, it is applied."""
        from app.services import brand_service, item_service

        # Save a brand preference
        brand_service.save_brand_preference("milk", "Organic Valley", user_id=1, db=db)

        # Add item without explicit brand
        items = item_service.add_items(
            items=[{"name": "milk"}],
            list_id=None,
            user_id=1,
            db=db,
        )
        assert len(items) == 1
        assert items[0].brand_pref == "Organic Valley"

    def test_explicit_brand_not_overridden(self, db):
        """If an explicit brand is given, it is NOT overridden by the saved preference."""
        from app.services import brand_service, item_service

        brand_service.save_brand_preference("milk", "Organic Valley", user_id=1, db=db)

        items = item_service.add_items(
            items=[{"name": "milk", "brand_hint": "Horizon"}],
            list_id=None,
            user_id=1,
            db=db,
        )
        assert items[0].brand_pref == "Horizon"

    def test_no_brand_preference_leaves_brand_empty(self, db):
        """If no preference exists and no brand given, brand_pref remains None."""
        from app.services import item_service

        items = item_service.add_items(
            items=[{"name": "apples"}],
            list_id=None,
            user_id=1,
            db=db,
        )
        assert items[0].brand_pref is None
