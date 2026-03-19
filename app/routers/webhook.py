"""
Webhook router — receives inbound SMS from Twilio.

POST /webhook/sms:
  1. Validate Twilio signature (skipped in development mode).
  2. Check idempotency via MessageSid.
  3. Look up user by phone number; send error SMS if unknown.
  4. Log the inbound message.
  5. Enqueue background task: orchestrator.handle_message.
  6. Return minimal TwiML <Response/>.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session
from twilio.request_validator import RequestValidator

from app.config import settings
from app.database import get_db
from app.services import message_service, sms_service
from app.services.user_service import get_user_by_phone
from app.agent import orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])

_TWIML_EMPTY = '<?xml version="1.0"?><Response/>'


@router.post("/sms")
async def receive_sms(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(...),
    X_Twilio_Signature: str = Header(default=""),
):
    # ------------------------------------------------------------------
    # 1. Validate Twilio signature (skip in development)
    # ------------------------------------------------------------------
    if settings.environment != "development":
        validator = RequestValidator(settings.twilio_auth_token)
        form_params = {"From": From, "Body": Body, "MessageSid": MessageSid}
        url = str(request.url)
        if not validator.validate(url, form_params, X_Twilio_Signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    # ------------------------------------------------------------------
    # 2. Idempotency — check for duplicate MessageSid
    # ------------------------------------------------------------------
    existing = message_service.get_by_twilio_sid(MessageSid, db)
    if existing is not None:
        logger.info("Duplicate MessageSid %s, skipping.", MessageSid)
        return Response(content=_TWIML_EMPTY, media_type="text/xml")

    # ------------------------------------------------------------------
    # 3. Look up user by phone number
    # ------------------------------------------------------------------
    user = get_user_by_phone(From, db)
    if user is None:
        logger.warning("Unknown phone number: %s", From)
        sms_service.send_error_sms(From)
        return Response(content=_TWIML_EMPTY, media_type="text/xml")

    # ------------------------------------------------------------------
    # 4. Log the inbound message
    # ------------------------------------------------------------------
    message_service.log_message(
        user_id=user.id,
        direction="INBOUND",
        body=Body,
        twilio_sid=MessageSid,
        db=db,
    )

    # ------------------------------------------------------------------
    # 5. Enqueue background task
    # ------------------------------------------------------------------
    background_tasks.add_task(orchestrator.handle_message, user.id, Body)

    # ------------------------------------------------------------------
    # 6. Return TwiML
    # ------------------------------------------------------------------
    return Response(content=_TWIML_EMPTY, media_type="text/xml")
