"""Item ORM model."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ItemStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("shopping_lists.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    quantity: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    brand_pref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ItemStatus.ACTIVE,
        server_default=ItemStatus.ACTIVE.value,
    )
    added_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    shopping_list: Mapped["ShoppingList"] = relationship("ShoppingList", back_populates="items")  # noqa: F821
    user: Mapped["User | None"] = relationship("User", foreign_keys=[added_by], back_populates="items")  # noqa: F821
    pending_confirmations: Mapped[list["PendingConfirmation"]] = relationship(  # noqa: F821
        "PendingConfirmation",
        foreign_keys="PendingConfirmation.item_id",
        back_populates="item",
    )
    pending_confirmations_as_existing: Mapped[list["PendingConfirmation"]] = relationship(  # noqa: F821
        "PendingConfirmation",
        foreign_keys="PendingConfirmation.existing_item_id",
        back_populates="existing_item",
    )

    def __repr__(self) -> str:
        return f"<Item id={self.id} name={self.name!r} status={self.status!r}>"
