"""
Tests for brand_service: get_brand_preference, save_brand_preference.
"""
import pytest
from sqlalchemy.orm import Session

from app.models import BrandPreference


class TestGetBrandPreference:
    def test_returns_none_when_no_preference_exists(self, db: Session):
        """get_brand_preference returns None if no record for item_name."""
        from app.services.brand_service import get_brand_preference

        result = get_brand_preference("milk", db)

        assert result is None

    def test_returns_preference_when_it_exists(self, db: Session):
        """get_brand_preference returns the stored BrandPreference record."""
        from app.services.brand_service import get_brand_preference

        pref = BrandPreference(item_name="butter", brand="Kerrygold")
        db.add(pref)
        db.commit()

        result = get_brand_preference("butter", db)

        assert result is not None
        assert result.item_name == "butter"
        assert result.brand == "Kerrygold"


class TestSaveBrandPreference:
    def test_creates_new_record_when_none_exists(self, db: Session):
        """save_brand_preference creates a new BrandPreference when none exists."""
        from app.services.brand_service import save_brand_preference

        result = save_brand_preference(item_name="eggs", brand="Happy Egg", user_id=1, db=db)

        assert result.id is not None
        assert result.item_name == "eggs"
        assert result.brand == "Happy Egg"

        # Verify the record is actually in the DB
        in_db = db.query(BrandPreference).filter(BrandPreference.item_name == "eggs").first()
        assert in_db is not None
        assert in_db.brand == "Happy Egg"

    def test_updates_existing_record_upsert_path(self, db: Session):
        """save_brand_preference updates the brand when a preference already exists."""
        from app.services.brand_service import save_brand_preference

        # Create an initial record
        existing = BrandPreference(item_name="cheese", brand="Tillamook")
        db.add(existing)
        db.commit()

        # Upsert with a new brand
        result = save_brand_preference(item_name="cheese", brand="Cabot", user_id=1, db=db)

        assert result.item_name == "cheese"
        assert result.brand == "Cabot"

        # Confirm only one record exists (no duplicate created)
        count = db.query(BrandPreference).filter(BrandPreference.item_name == "cheese").count()
        assert count == 1

    def test_case_insensitive_save_and_lookup(self, db: Session):
        """Saving with mixed case and looking up with different case returns the same preference."""
        from app.services.brand_service import get_brand_preference, save_brand_preference

        # Save with title-case item name
        save_brand_preference(item_name="Milk", brand="Organic Valley", user_id=1, db=db)

        # Look up with lowercase — should find the same record
        result = get_brand_preference("milk", db)
        assert result is not None
        assert result.item_name == "milk"
        assert result.brand == "Organic Valley"

        # Look up with uppercase — should also find it
        result_upper = get_brand_preference("MILK", db)
        assert result_upper is not None
        assert result_upper.brand == "Organic Valley"

        # Confirm only one record was created (no duplicates from different cases)
        count = db.query(BrandPreference).filter(BrandPreference.item_name == "milk").count()
        assert count == 1
