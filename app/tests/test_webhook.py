"""
Tests for POST /webhook/sms endpoint.

TDD: these tests are written before the implementation.

Test cases:
- Valid Twilio signature → 200 response, background task enqueued
- Invalid Twilio signature → 403 response
- Duplicate MessageSid → 200, no processing (idempotency)
- Unknown phone number → 200, SMS error reply sent, no agent call
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_db
from app.models import User, Message
from app.models.message import MessageDirection


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_form(from_: str, body: str = "add milk", sid: str = "SM123") -> dict:
    return {
        "From": from_,
        "Body": body,
        "MessageSid": sid,
    }


def _webhook_client(db, validate_return: bool = True) -> TestClient:
    """
    Build a TestClient for the webhook router with:
    - db dependency overridden
    - Twilio signature validation patched to return validate_return
    - environment set to 'production' so validation is not skipped
    """
    from app.routers.webhook import router as webhook_router

    test_app = FastAPI()

    def override_get_db():
        yield db

    test_app.include_router(webhook_router)
    test_app.dependency_overrides[get_db] = override_get_db

    return TestClient(test_app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWebhookSms:
    def test_valid_signature_enqueues_task(self, db):
        """Valid Twilio signature → 200 and background task is enqueued."""
        form = _make_form(from_=settings.chris_phone, sid="SM_valid_001")

        with patch("app.routers.webhook.settings") as mock_settings, \
             patch("app.routers.webhook.RequestValidator") as mock_validator_cls, \
             patch("app.routers.webhook.orchestrator") as mock_orchestrator:

            mock_settings.environment = "production"
            mock_settings.twilio_auth_token = "fake_token"
            mock_validator = MagicMock()
            mock_validator.validate.return_value = True
            mock_validator_cls.return_value = mock_validator

            client = _webhook_client(db)
            response = client.post(
                "/webhook/sms",
                data=form,
                headers={"X-Twilio-Signature": "fake_sig"},
            )

        assert response.status_code == 200
        assert "text/xml" in response.headers["content-type"]
        assert "<Response" in response.text

    def test_invalid_signature_returns_403(self, db):
        """Invalid Twilio signature → 403."""
        form = _make_form(from_=settings.chris_phone, sid="SM_invalid_001")

        with patch("app.routers.webhook.settings") as mock_settings, \
             patch("app.routers.webhook.RequestValidator") as mock_validator_cls:

            mock_settings.environment = "production"
            mock_settings.twilio_auth_token = "fake_token"
            mock_validator = MagicMock()
            mock_validator.validate.return_value = False
            mock_validator_cls.return_value = mock_validator

            client = _webhook_client(db)
            response = client.post(
                "/webhook/sms",
                data=form,
                headers={"X-Twilio-Signature": "bad_sig"},
            )

        assert response.status_code == 403

    def test_duplicate_message_sid_returns_200_no_processing(self, db):
        """Duplicate MessageSid → 200 with no agent processing (idempotency)."""
        user = db.query(User).filter_by(name="Chris").first()
        # Pre-insert a message with the same SID
        db.add(Message(
            user_id=user.id,
            direction=MessageDirection.INBOUND,
            body="add milk",
            twilio_sid="SM_duplicate_001",
        ))
        db.commit()

        from_ = settings.chris_phone
        form = _make_form(from_=from_, sid="SM_duplicate_001")

        with patch("app.routers.webhook.settings") as mock_settings, \
             patch("app.routers.webhook.RequestValidator") as mock_validator_cls, \
             patch("app.routers.webhook.orchestrator") as mock_orchestrator:

            mock_settings.environment = "production"
            mock_settings.twilio_auth_token = "fake_token"
            mock_validator = MagicMock()
            mock_validator.validate.return_value = True
            mock_validator_cls.return_value = mock_validator

            client = _webhook_client(db)
            response = client.post(
                "/webhook/sms",
                data=form,
                headers={"X-Twilio-Signature": "fake_sig"},
            )

            # Orchestrator must NOT be called for duplicate SIDs
            mock_orchestrator.handle_message.assert_not_called()

        assert response.status_code == 200

    def test_unknown_phone_sends_error_sms_and_returns_200(self, db):
        """Unknown phone number → 200, error SMS sent, no agent call."""
        unknown_phone = "+15559999999"
        form = _make_form(from_=unknown_phone, sid="SM_unknown_001")

        with patch("app.routers.webhook.settings") as mock_settings, \
             patch("app.routers.webhook.RequestValidator") as mock_validator_cls, \
             patch("app.routers.webhook.orchestrator") as mock_orchestrator, \
             patch("app.routers.webhook.sms_service") as mock_sms:

            mock_settings.environment = "production"
            mock_settings.twilio_auth_token = "fake_token"
            mock_validator = MagicMock()
            mock_validator.validate.return_value = True
            mock_validator_cls.return_value = mock_validator

            client = _webhook_client(db)
            response = client.post(
                "/webhook/sms",
                data=form,
                headers={"X-Twilio-Signature": "fake_sig"},
            )

            # No agent call
            mock_orchestrator.handle_message.assert_not_called()
            # Error SMS sent
            mock_sms.send_error_sms.assert_called_once_with(unknown_phone)

        assert response.status_code == 200

    def test_development_mode_skips_validation(self, db):
        """In development environment, signature validation is skipped."""
        form = _make_form(from_=settings.chris_phone, sid="SM_dev_001")

        with patch("app.routers.webhook.settings") as mock_settings, \
             patch("app.routers.webhook.orchestrator"):

            mock_settings.environment = "development"
            mock_settings.twilio_auth_token = "fake_token"

            client = _webhook_client(db)
            # No X-Twilio-Signature header — would fail in production
            response = client.post("/webhook/sms", data=form)

        assert response.status_code == 200
