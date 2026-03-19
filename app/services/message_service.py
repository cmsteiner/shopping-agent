"""Message service — log and look up SMS messages."""
from sqlalchemy.orm import Session

from app.models import Message
from app.models.message import MessageDirection


def log_message(
    user_id: int,
    direction: str,
    body: str,
    twilio_sid: str | None,
    db: Session,
) -> Message:
    """Persist an inbound or outbound message record and return it."""
    msg = Message(
        user_id=user_id,
        direction=MessageDirection(direction),
        body=body,
        twilio_sid=twilio_sid,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_by_twilio_sid(twilio_sid: str, db: Session) -> Message | None:
    """Return the Message with the given Twilio SID, or None."""
    return db.query(Message).filter(Message.twilio_sid == twilio_sid).first()
