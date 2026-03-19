"""
Duplicate detection service.

Uses rapidfuzz fuzzy matching to identify items on the new-items list that
closely match items already on the active shopping list.
"""
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Item, ShoppingList
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus


def check_duplicates(new_items: list[dict], db: Session) -> dict:
    """
    Check new_items for fuzzy matches against the current ACTIVE list.

    Parameters
    ----------
    new_items : list[dict]
        Each dict must contain at least a "name" key.
    db : Session

    Returns
    -------
    dict with two keys:
        "clear" : list[dict]
            Items whose best match score is below the threshold.
        "possible_duplicates" : list[tuple[dict, Item, float]]
            (new_item, existing_item, score) triples where score >= threshold.
    """
    threshold = settings.duplicate_threshold

    # Load all ACTIVE items from the current ACTIVE list
    active_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.ACTIVE)
        .first()
    )

    existing_items: list[Item] = []
    if active_list is not None:
        existing_items = (
            db.query(Item)
            .filter(
                Item.list_id == active_list.id,
                Item.status == ItemStatus.ACTIVE,
            )
            .all()
        )

    clear: list[dict] = []
    possible_duplicates: list[tuple[dict, Item, float]] = []

    for new_item in new_items:
        new_name = new_item.get("name", "")
        best_score = 0.0
        best_existing: Item | None = None

        for existing in existing_items:
            score = fuzz.token_set_ratio(new_name, existing.name)
            if score > best_score:
                best_score = score
                best_existing = existing

        if best_score >= threshold and best_existing is not None:
            possible_duplicates.append((new_item, best_existing, best_score))
        else:
            clear.append(new_item)

    return {
        "clear": clear,
        "possible_duplicates": possible_duplicates,
    }
