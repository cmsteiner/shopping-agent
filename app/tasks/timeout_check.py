"""
Timeout check task — identifies shopping lists that have been SENT for too long
and sends a timeout SMS to all users.

Idempotency: if a timeout prompt has already been sent after the list was sent,
the list is skipped.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Message, ShoppingList
from app.models.shopping_list import ListStatus
from app.models.message import MessageDirection
from app.services import sms_service, message_service
from app.services.user_service import get_all_users

logger = logging.getLogger(__name__)

TIMEOUT_MESSAGE = (
    "Did you finish your shopping trip? "
    "Reply DONE to clear the list or CANCEL to keep it."
)


def run_timeout_check(db: Session) -> int:
    """
    Check for timed-out shopping lists and send timeout SMS to all users.

    Returns the count of lists that triggered a timeout SMS.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.trip_timeout_hours)

    sent_lists = (
        db.query(ShoppingList)
        .filter(
            ShoppingList.status == ListStatus.SENT,
            ShoppingList.sent_at < cutoff,
        )
        .all()
    )

    count = 0
    for lst in sent_lists:
        if message_service.has_timeout_prompt_been_sent(lst.sent_at, lst.id, db):
            logger.info("Timeout prompt already sent for list id=%s, skipping.", lst.id)
            continue

        users = get_all_users(db)
        try:
            # Phase 1: send all SMSs; collect Message objects to persist
            pending_messages = []
            for user in users:
                sms_service.send_sms(user.phone_number, TIMEOUT_MESSAGE)
                pending_messages.append(
                    Message(
                        user_id=user.id,
                        direction=MessageDirection.OUTBOUND,
                        body=TIMEOUT_MESSAGE,
                        twilio_sid=None,
                    )
                )
                logger.info(
                    "Sent timeout SMS to user id=%s (phone=%s) for list id=%s.",
                    user.id,
                    user.phone_number,
                    lst.id,
                )

            # Phase 2: commit all message records in a single transaction
            for msg in pending_messages:
                db.add(msg)
            db.commit()
        except Exception:
            logger.exception("Failed to process timeout for list id=%s, skipping.", lst.id)
            db.rollback()
            continue

        count += 1

    return count
