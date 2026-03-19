"""User service — database lookups for User records."""
from sqlalchemy.orm import Session

from app.models import User


def get_user_by_phone(phone: str, db: Session) -> User | None:
    """Return User with the given phone number, or None if not found."""
    return db.query(User).filter(User.phone_number == phone).first()


def get_user_by_id(user_id: int, db: Session) -> User:
    """Return User by primary key. Raises if not found."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise ValueError(f"User with id={user_id} not found")
    return user
