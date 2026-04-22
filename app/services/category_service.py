"""Category service."""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Category, Item
from app.services.realtime_service import record_event


def _normalize_name(name: str) -> str:
    return name.strip().lower()


def create_category(name: str, db: Session) -> Category:
    """Create a category unless one with the same normalized name already exists."""
    normalized_name = _normalize_name(name)
    existing = (
        db.query(Category)
        .filter(Category.normalized_name == normalized_name)
        .first()
    )
    if existing is not None:
        return existing

    max_sort_order = db.query(func.max(Category.sort_order)).scalar()
    category = Category(
        name=name.strip(),
        normalized_name=normalized_name,
        sort_order=(max_sort_order or 0) + 10,
    )
    db.add(category)
    db.flush()
    record_event(
        list_id=None,
        event_type="category.created",
        entity_type="category",
        entity_id=category.id,
        payload={"id": category.id, "name": category.name},
        db=db,
    )
    db.commit()
    db.refresh(category)
    return category


def rename_category(category_id: int, new_name: str, db: Session) -> Category:
    """Rename a category and update linked item category text."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise ValueError(f"Category with id={category_id} not found.")

    category.name = new_name.strip()
    category.normalized_name = _normalize_name(new_name)
    category.updated_at = datetime.now(timezone.utc)
    category.version += 1

    (
        db.query(Item)
        .filter(Item.category_id == category.id)
        .update({"category": category.name}, synchronize_session=False)
    )

    record_event(
        list_id=None,
        event_type="category.updated",
        entity_type="category",
        entity_id=category.id,
        payload={"id": category.id, "name": category.name},
        db=db,
    )
    db.commit()
    db.refresh(category)
    return category


def delete_category(category_id: int, db: Session) -> None:
    """Delete a category if it contains no items."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if category is None:
        raise ValueError(f"Category with id={category_id} not found.")

    has_items = db.query(Item).filter(Item.category_id == category.id).first()
    if has_items is not None:
        raise ValueError("Move all items out of this category before deleting it.")

    record_event(
        list_id=None,
        event_type="category.deleted",
        entity_type="category",
        entity_id=category.id,
        payload={"id": category.id, "name": category.name},
        db=db,
    )
    db.delete(category)
    db.commit()
