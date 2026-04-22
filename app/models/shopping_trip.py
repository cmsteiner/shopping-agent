"""ShoppingTrip ORM model."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TripStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


class ShoppingTrip(Base):
    __tablename__ = "shopping_trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("shopping_lists.id"), nullable=False)
    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=TripStatus.ACTIVE,
        server_default=TripStatus.ACTIVE.value,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    shopping_list: Mapped["ShoppingList"] = relationship("ShoppingList", back_populates="trips")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ShoppingTrip id={self.id} status={self.status!r}>"
