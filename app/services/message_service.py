"""Message service — log and look up SMS messages."""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Message
from app.models.message import MessageDirection

# Sentinel substring used to detect timeout prompts in the messages table.
_TIMEOUT_PROMPT_MARKER = "Did you finish"


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


def has_timeout_prompt_been_sent(sent_at: datetime, db: Session) -> bool:
    """
    Check whether a timeout prompt has already been sent after the given
    sent_at datetime.  Uses the TIMEOUT_MESSAGE constant as the search key.
    """
    existing = (
        db.query(Message)
        .filter(
            Message.direction == MessageDirection.OUTBOUND,
            Message.body.contains(_TIMEOUT_PROMPT_MARKER),
            Message.created_at > sent_at,
        )
        .first()
    )
    return existing is not None
