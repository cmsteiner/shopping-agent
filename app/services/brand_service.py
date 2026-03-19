"""
Brand preference service.

Handles lookup and upsert of BrandPreference records.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import BrandPreference


def get_brand_preference(item_name: str, db: Session) -> BrandPreference | None:
    """Return the stored BrandPreference for item_name, or None."""
    return (
        db.query(BrandPreference)
        .filter(BrandPreference.item_name == item_name)
        .first()
    )


def save_brand_preference(
    item_name: str, brand: str, user_id: int, db: Session
) -> BrandPreference:
    """
    Upsert a BrandPreference.

    If a preference for item_name already exists it is updated; otherwise a
    new record is created.

    Parameters
    ----------
    item_name : str
        The generic item name (e.g. "milk").
    brand : str
        The preferred brand (e.g. "Organic Valley").
    user_id : int
        The user making the change (stored as set_by).
    db : Session

    Returns
    -------
    BrandPreference
        The created or updated record.
    """
    pref = get_brand_preference(item_name, db)
    if pref is not None:
        pref.brand = brand
        pref.set_by = user_id
        pref.updated_at = datetime.now(timezone.utc)
    else:
        pref = BrandPreference(
            item_name=item_name,
            brand=brand,
            set_by=user_id,
        )
        db.add(pref)

    db.commit()
    db.refresh(pref)
    return pref
