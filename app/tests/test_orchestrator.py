"""
Tests for the agent orchestrator.

TDD: these tests are written before the implementation.

Test cases:
- Mock Anthropic returns parse_items → add_items → end_turn with text
- Assert item is written to DB and SMS is sent to the user
"""
import pytest
from unittest.mock import patch, MagicMock, call
from sqlalchemy.orm import Session

from app.tests.conftest import MockAnthropicClient, MockTwilioTracker

from app.config import settings
from app.models import User, Item, ShoppingList
from app.models.shopping_list import ListStatus
from app.models.item import ItemStatus


# ---------------------------------------------------------------------------
# Helpers to build mock Anthropic response objects
# ---------------------------------------------------------------------------

def make_tool_use_block(tool_name: str, tool_input: dict, tool_id: str):
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id
    return block


def make_text_block(text: str):
    """Create a mock text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tu1"):
    """Create a mock Claude response with stop_reason='tool_use'."""
    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [make_tool_use_block(tool_name, tool_input, tool_id)]
    return response


def make_end_turn_response(text: str):
    """Create a mock Claude response with stop_reason='end_turn'."""
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [make_text_block(text)]
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrchestratorFlow:
    def test_add_item_flow(self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient):
        """
        Full happy-path flow:
          1. Claude returns parse_items tool call
          2. Claude returns add_items tool call
          3. Claude returns end_turn with confirmation text
        Asserts: item written to DB, final SMS sent to user.
        """
        # Create an active shopping list for the test
        shopping_list = ShoppingList(status=ListStatus.ACTIVE)
        db.add(shopping_list)
        db.commit()
        db.refresh(shopping_list)

        mock_anthropic.set_responses([
            make_tool_use_response(
                "parse_items",
                {"text": "add milk"},
                tool_id="tu1",
            ),
            make_tool_use_response(
                "add_items",
                {"items": [{"name": "milk"}], "list_id": shopping_list.id},
                tool_id="tu2",
            ),
            make_end_turn_response("Added milk to your list!"),
        ])

        user = db.query(User).filter_by(name="Chris").first()

        from app.agent import orchestrator
        orchestrator.handle_message(user.id, "add milk", db=db)

        # Item must be in the DB
        items = db.query(Item).all()
        assert len(items) == 1
        assert items[0].name == "milk"

        # Confirmation SMS must have been sent
        assert len(mock_twilio.sent_messages) >= 1
        assert mock_twilio.sent_messages[-1]["body"] == "Added milk to your list!"
        assert mock_twilio.sent_messages[-1]["to"] == user.phone_number

    def test_fallback_on_loop_exhaustion(self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient):
        """
        When the tool-use loop is exhausted (no end_turn), a fallback SMS is sent.
        """
        # Always return tool_use — never end_turn
        mock_anthropic.set_responses([
            make_tool_use_response("parse_items", {"text": "add milk"}, tool_id=f"tu{i}")
            for i in range(11)  # more than max iterations
        ])

        user = db.query(User).filter_by(name="Chris").first()

        from app.agent import orchestrator
        orchestrator.handle_message(user.id, "add milk", db=db)

        assert len(mock_twilio.sent_messages) >= 1
        assert "trouble" in mock_twilio.sent_messages[-1]["body"].lower()

    def test_exception_sends_fallback_sms(self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient):
        """
        On unhandled exception, the fallback SMS is sent and no exception propagates.
        """
        mock_anthropic.set_responses([])  # no responses — will raise on first create call

        # Force the first create call to raise
        import anthropic as anthropic_module
        with patch("app.agent.orchestrator.anthropic.Anthropic") as bad_client_cls:
            bad_client = MagicMock()
            bad_client.messages.create.side_effect = RuntimeError("API failure")
            bad_client_cls.return_value = bad_client

            with patch("app.agent.orchestrator.sms_service") as mock_svc:
                sent = []
                mock_svc.send_sms.side_effect = lambda to, body: sent.append({"to": to, "body": body})
                mock_svc.send_error_sms.side_effect = lambda to: sent.append({"to": to, "body": "__error__"})

                user = db.query(User).filter_by(name="Chris").first()

                from app.agent import orchestrator
                # Must not raise
                orchestrator.handle_message(user.id, "add milk", db=db)

                assert len(sent) >= 1
                assert "trouble" in sent[-1]["body"].lower()


class TestOrchestratorPhase3:
    """Extended orchestrator tests for Phase 3 commands."""

    def test_done_command_calls_archive_list(
        self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient
    ):
        """DONE command → archive_list tool called, list gets archived."""
        from app.agent import orchestrator

        # Create a SENT list (archive_list requires SENT)
        sl = ShoppingList(status=ListStatus.SENT)
        db.add(sl)
        db.commit()
        db.refresh(sl)

        mock_anthropic.set_responses([
            make_tool_use_response("archive_list", {}, tool_id="tu1"),
            make_end_turn_response("Done! Shopping trip archived."),
        ])

        user = db.query(User).filter_by(name="Chris").first()
        orchestrator.handle_message(user.id, "done", db=db)

        # The original list should now be ARCHIVED
        db.refresh(sl)
        assert sl.status == ListStatus.ARCHIVED

        # A new ACTIVE list should exist
        new_active = (
            db.query(ShoppingList).filter(ShoppingList.status == ListStatus.ACTIVE).first()
        )
        assert new_active is not None

        # SMS should have been sent
        assert any("archived" in m["body"].lower() or "done" in m["body"].lower()
                   for m in mock_twilio.sent_messages)

    def test_cancel_command_list_stays_active(
        self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient
    ):
        """CANCEL command → no archive, list stays ACTIVE."""
        from app.agent import orchestrator

        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.commit()
        db.refresh(sl)

        # Claude just ends the turn with a cancel confirmation, no archive_list call
        mock_anthropic.set_responses([
            make_end_turn_response("No problem, cancelled."),
        ])

        user = db.query(User).filter_by(name="Chris").first()
        orchestrator.handle_message(user.id, "cancel", db=db)

        # List must still be ACTIVE
        db.refresh(sl)
        assert sl.status == ListStatus.ACTIVE

    def test_duplicate_detected_hold_pending_called(
        self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient
    ):
        """Duplicate detected → hold_pending called, PENDING item created, confirmation SMS sent."""
        from app.agent import orchestrator

        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        existing = Item(list_id=sl.id, name="milk", status=ItemStatus.ACTIVE)
        db.add(existing)
        db.commit()
        db.refresh(existing)

        mock_anthropic.set_responses([
            make_tool_use_response(
                "hold_pending",
                {"item": {"name": "milk"}, "existing_item_id": existing.id},
                tool_id="tu1",
            ),
            make_end_turn_response(
                "Milk might already be on the list — reply 'yes add it' or 'skip milk'."
            ),
        ])

        user = db.query(User).filter_by(name="Chris").first()
        orchestrator.handle_message(user.id, "add milk", db=db)

        # A PENDING item must have been created
        pending_items = (
            db.query(Item).filter(Item.status == ItemStatus.PENDING).all()
        )
        assert len(pending_items) == 1
        assert pending_items[0].name == "milk"

        # SMS should mention the duplicate
        last_msg = mock_twilio.sent_messages[-1]["body"]
        assert "milk" in last_msg.lower()

    def test_preview_does_not_change_list_status(
        self, db: Session, mock_twilio: MockTwilioTracker, mock_anthropic: MockAnthropicClient
    ):
        """PREVIEW → get_list called, list status unchanged (no send_list transition)."""
        from app.agent import orchestrator

        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        db.add(Item(list_id=sl.id, name="milk", status=ItemStatus.ACTIVE, category="Dairy"))
        db.commit()
        db.refresh(sl)

        # Claude calls get_list, then ends turn with formatted list (does NOT call send_list)
        mock_anthropic.set_responses([
            make_tool_use_response("get_list", {}, tool_id="tu1"),
            make_end_turn_response("Here's your list:\nDairy:\n- milk"),
        ])

        user = db.query(User).filter_by(name="Chris").first()
        orchestrator.handle_message(user.id, "preview", db=db)

        # List status must remain ACTIVE
        db.refresh(sl)
        assert sl.status == ListStatus.ACTIVE

        # SMS should have been sent to the requester
        assert len(mock_twilio.sent_messages) >= 1
        assert mock_twilio.sent_messages[-1]["to"] == user.phone_number
