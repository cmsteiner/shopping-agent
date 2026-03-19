"""User ORM model."""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)

    # Relationships (back-populated by child models)
    items: Mapped[list["Item"]] = relationship("Item", foreign_keys="Item.added_by", back_populates="user")  # noqa: F821
    messages: Mapped[list["Message"]] = relationship("Message", back_populates="user")  # noqa: F821
    brand_preferences: Mapped[list["BrandPreference"]] = relationship("BrandPreference", back_populates="user")  # noqa: F821
    pending_confirmations: Mapped[list["PendingConfirmation"]] = relationship("PendingConfirmation", back_populates="user")  # noqa: F821

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.name!r} phone={self.phone_number!r}>"
