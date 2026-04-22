"""
ORM models package. Imports all models so SQLAlchemy's metadata is fully populated
and foreign-key relationships resolve correctly.
"""
from app.models.base import Base
from app.models.category import Category
from app.models.user import User
from app.models.shopping_list import ShoppingList
from app.models.shopping_trip import ShoppingTrip
from app.models.item import Item
from app.models.list_event import ListEvent
from app.models.brand_preference import BrandPreference
from app.models.message import Message
from app.models.pending_confirmation import PendingConfirmation

__all__ = [
    "Base",
    "Category",
    "User",
    "ShoppingList",
    "ShoppingTrip",
    "Item",
    "ListEvent",
    "BrandPreference",
    "Message",
    "PendingConfirmation",
]
