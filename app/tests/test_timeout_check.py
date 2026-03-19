"""
Tests for POST /tasks/timeout-check endpoint and run_timeout_check logic.

TDD: tests written before implementation.

Test cases:
- List SENT 9 hours ago, no prior timeout prompt → both users receive timeout SMS
- List SENT 7 hours ago → skipped (not timed out yet)
- List SENT 9 hours ago, timeout prompt already sent → skipped (idempotency)
- Cron endpoint called without valid X-Cron-Secret → 403
- Cron endpoint called with valid X-Cron-Secret → 200
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ShoppingList, User, Message
from app.models.shopping_list import ListStatus
from app.models.message import MessageDirection
from app.tasks.timeout_check import TIMEOUT_MESSAGE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tasks_client(db: Session) -> TestClient:
    """Build a TestClient for the tasks router with db overridden."""
    from app.routers.tasks import router as tasks_router

    test_app = FastAPI()

    def override_get_db():
        yield db

    test_app.include_router(tasks_router)
    test_app.dependency_overrides[get_db] = override_get_db

    return TestClient(test_app, raise_server_exceptions=True)


def _make_sent_list(db: Session, hours_ago: float) -> ShoppingList:
    """Create a ShoppingList with SENT status and sent_at hours_ago."""
    sent_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    sl = ShoppingList(status=ListStatus.SENT, sent_at=sent_at)
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return sl


# ---------------------------------------------------------------------------
# Unit tests for run_timeout_check logic
# ---------------------------------------------------------------------------

class TestTimeoutCheckLogic:
    def test_timed_out_list_sends_sms_to_both_users(self, db: Session):
        """List SENT 9 hours ago, no prior timeout prompt → both users get timeout SMS."""
        _make_sent_list(db, hours_ago=9)

        sent_messages = []

        def fake_send_sms(to: str, body: str) -> str:
            sent_messages.append({"to": to, "body": body})
            return "SM_fake"

        with patch("app.tasks.timeout_check.sms_service") as mock_svc:
            mock_svc.send_sms.side_effect = fake_send_sms

            from app.tasks.timeout_check import run_timeout_check
            count = run_timeout_check(db)

        assert count == 1
        recipients = {m["to"] for m in sent_messages}
        assert settings.chris_phone in recipients
        assert settings.donna_phone in recipients
        assert all(TIMEOUT_MESSAGE in m["body"] for m in sent_messages)

    def test_not_timed_out_list_is_skipped(self, db: Session):
        """List SENT 7 hours ago → skipped, no SMS sent."""
        _make_sent_list(db, hours_ago=7)

        with patch("app.tasks.timeout_check.sms_service") as mock_svc:
            from app.tasks.timeout_check import run_timeout_check
            count = run_timeout_check(db)

        assert count == 0
        mock_svc.send_sms.assert_not_called()

    def test_timeout_prompt_already_sent_is_skipped(self, db: Session):
        """List SENT 9 hours ago, timeout prompt already sent → skipped (idempotency)."""
        sl = _make_sent_list(db, hours_ago=9)

        # Log a prior timeout message with created_at within the 1-hour idempotency
        # window (sent_at to sent_at + 1h) so the scoped check detects it.
        user = db.query(User).filter_by(name="Chris").first()
        msg = Message(
            user_id=user.id,
            direction=MessageDirection.OUTBOUND,
            body=TIMEOUT_MESSAGE,
            twilio_sid=None,
            created_at=sl.sent_at + timedelta(minutes=30),
        )
        db.add(msg)
        db.commit()

        with patch("app.tasks.timeout_check.sms_service") as mock_svc:
            from app.tasks.timeout_check import run_timeout_check
            count = run_timeout_check(db)

        assert count == 0
        mock_svc.send_sms.assert_not_called()

    def test_active_list_not_included(self, db: Session):
        """ACTIVE list (not SENT) is not checked for timeout."""
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.commit()

        with patch("app.tasks.timeout_check.sms_service") as mock_svc:
            from app.tasks.timeout_check import run_timeout_check
            count = run_timeout_check(db)

        assert count == 0
        mock_svc.send_sms.assert_not_called()


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestTimeoutCheckEndpoint:
    def test_missing_secret_returns_403(self, db: Session):
        """Request without X-Cron-Secret header → 403."""
        client = _make_tasks_client(db)
        response = client.post("/tasks/timeout-check")
        assert response.status_code == 403

    def test_invalid_secret_returns_403(self, db: Session):
        """Request with wrong X-Cron-Secret → 403."""
        client = _make_tasks_client(db)
        response = client.post(
            "/tasks/timeout-check",
            headers={"X-Cron-Secret": "wrong-secret"},
        )
        assert response.status_code == 403

    def test_valid_secret_returns_200(self, db: Session):
        """Request with correct X-Cron-Secret → 200 with status ok."""
        client = _make_tasks_client(db)

        with patch("app.routers.tasks.settings") as mock_settings, \
             patch("app.routers.tasks.run_timeout_check", return_value=0):
            mock_settings.webhook_secret = "test-secret"

            response = client.post(
                "/tasks/timeout-check",
                headers={"X-Cron-Secret": "test-secret"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "checked" in data

    def test_valid_secret_returns_checked_count(self, db: Session):
        """Endpoint returns correct count of lists checked."""
        client = _make_tasks_client(db)

        with patch("app.routers.tasks.settings") as mock_settings, \
             patch("app.routers.tasks.run_timeout_check", return_value=3):
            mock_settings.webhook_secret = "test-secret"

            response = client.post(
                "/tasks/timeout-check",
                headers={"X-Cron-Secret": "test-secret"},
            )

        assert response.status_code == 200
        assert response.json()["checked"] == 3
