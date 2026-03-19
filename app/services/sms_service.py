"""SMS service — send messages via Twilio."""
from twilio.rest import Client

from app.config import settings

_ERROR_MESSAGE = (
    "Sorry, I don't recognise your number. "
    "Please contact the household admin to get set up."
)


def _get_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def send_sms(to: str, body: str) -> str:
    """Send an SMS via Twilio and return the message SID."""
    client = _get_client()
    message = client.messages.create(
        body=body,
        from_=settings.twilio_phone_number,
        to=to,
    )
    return message.sid


def send_error_sms(to: str) -> None:
    """Send a generic 'unknown number' error SMS."""
    send_sms(to, _ERROR_MESSAGE)
