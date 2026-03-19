"""PendingConfirmation ORM model."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PendingConfirmation(Base):
    __tablename__ = "pending_confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("items.id"), nullable=False)
    existing_item_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("items.id"), nullable=True)
    triggered_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    item: Mapped["Item"] = relationship(  # noqa: F821
        "Item",
        foreign_keys=[item_id],
        back_populates="pending_confirmations",
    )
    existing_item: Mapped["Item | None"] = relationship(  # noqa: F821
        "Item",
        foreign_keys=[existing_item_id],
        back_populates="pending_confirmations_as_existing",
    )
    user: Mapped["User"] = relationship("User", back_populates="pending_confirmations")  # noqa: F821

    def __repr__(self) -> str:
        return f"<PendingConfirmation id={self.id} item_id={self.item_id}>"
