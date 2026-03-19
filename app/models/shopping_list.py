"""ShoppingList ORM model."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ListStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SENT = "SENT"
    ARCHIVED = "ARCHIVED"


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[ListStatus] = mapped_column(
        Enum(ListStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ListStatus.ACTIVE,
        server_default=ListStatus.ACTIVE.value,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    items: Mapped[list["Item"]] = relationship("Item", back_populates="shopping_list", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ShoppingList id={self.id} status={self.status!r}>"
