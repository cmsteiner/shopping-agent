"""
Tests for the agent orchestrator.

TDD: these tests are written before the implementation.

Test cases:
- Mock Anthropic returns parse_items → add_items → end_turn with text
- Assert item is written to DB and SMS is sent to the user
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session

from app.tests.conftest import MockAnthropicClient, MockTwilioTracker

from app.config import settings
from app.models import User, Item, ShoppingList
from app.models.shopping_list import ListStatus


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
