"""ListEvent ORM model."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ListEvent(Base):
    __tablename__ = "list_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    list_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("shopping_lists.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    shopping_list: Mapped["ShoppingList | None"] = relationship("ShoppingList", back_populates="events")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ListEvent id={self.id} event_type={self.event_type!r}>"
