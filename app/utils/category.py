"""
Category normalization utilities.

Provides a canonical ordering of grocery categories and a function to
normalize raw category strings to the canonical set.
"""

CANONICAL_CATEGORIES: list[str] = [
    "PRODUCE",
    "DAIRY",
    "MEAT",
    "SEAFOOD",
    "BAKERY",
    "FROZEN",
    "PANTRY",
    "BEVERAGES",
    "SNACKS",
    "CLEANING",
    "PERSONAL CARE",
    "HOUSEHOLD",
    "OTHER",
]

_CANONICAL_UPPER: dict[str, str] = {cat.upper(): cat for cat in CANONICAL_CATEGORIES}


def normalize_category(category: str) -> str:
    """
    Normalize a raw category string to one of the canonical categories.

    Matching is case-insensitive. Unknown categories fall back to "OTHER".

    Parameters
    ----------
    category : str
        Raw category string (e.g. "dairy", "Produce", "MEAT").

    Returns
    -------
    str
        The canonical category name (e.g. "DAIRY", "PRODUCE", "OTHER").
    """
    if not category:
        return "OTHER"
    normalized = _CANONICAL_UPPER.get(category.strip().upper())
    return normalized if normalized is not None else "OTHER"
