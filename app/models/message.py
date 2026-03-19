"""Message ORM model."""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MessageDirection(str, enum.Enum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    twilio_sid: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="messages")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Message id={self.id} direction={self.direction!r} sid={self.twilio_sid!r}>"
