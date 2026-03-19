"""
Orchestrator — drives the Claude tool-use loop for each inbound SMS.

handle_message(user_id, body, db=None):
  - Accepts an optional db session (used in tests to avoid creating a new session).
  - Builds the system prompt.
  - Calls Claude with the full tool set.
  - Executes tool calls and feeds results back until end_turn or max iterations.
  - Sends the final response via SMS.
  - On any exception, sends a fallback SMS.
"""
import logging

import anthropic

from app.config import settings
from app.database import SessionLocal
from app.services import sms_service
from app.services.message_service import log_message
from app.services.user_service import get_user_by_id
from app.agent import context_builder, tool_executor
from app.agent.tool_definitions import TOOLS

logger = logging.getLogger(__name__)

_MAX_ITERATIONS = 10
_FALLBACK_MESSAGE = "Sorry, I had trouble processing that. Please try again."


def _select_model(system_prompt: str) -> str:
    """
    Use Haiku for simple requests; Sonnet when context is richer
    (pending items or multiple items with brands detected in the prompt).
    """
    prompt_lower = system_prompt.lower()
    use_sonnet = (
        "pending" in prompt_lower
        or ("brand" in prompt_lower and prompt_lower.count("-") > 2)
    )
    return settings.sonnet_model if use_sonnet else settings.haiku_model


def handle_message(user_id: int, body: str, db=None) -> None:
    """
    Process an inbound SMS message through the Claude tool-use loop.

    Parameters
    ----------
    user_id : int
        The ID of the user who sent the message.
    body : str
        The raw SMS text.
    db : Session, optional
        Database session.  When provided (e.g. in tests) it is used directly
        and NOT closed on exit.  When omitted a new session is created and
        managed internally.
    """
    _owns_db = db is None
    if _owns_db:
        db = SessionLocal()

    user_phone: str | None = None
    try:
        user = get_user_by_id(user_id, db)
        user_phone = user.phone_number  # Cache before any DB operations

        # Note: the inbound message is logged by the webhook router (with its
        # Twilio SID) before this background task is enqueued. We do NOT
        # re-log here to avoid duplicates.

        system_prompt = context_builder.build_system_prompt(user, db)
        model = _select_model(system_prompt)

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        messages = [{"role": "user", "content": body}]

        for _ in range(_MAX_ITERATIONS):
            response = client.messages.create(
                model=model,
                system=system_prompt,
                tools=TOOLS,
                messages=messages,
                max_tokens=1024,
            )

            if response.stop_reason == "end_turn":
                text = next(
                    (b.text for b in response.content if b.type == "text"),
                    _FALLBACK_MESSAGE,
                )
                sms_service.send_sms(user.phone_number, text)
                # Log outbound
                log_message(
                    user_id=user_id,
                    direction="OUTBOUND",
                    body=text,
                    twilio_sid=None,
                    db=db,
                )
                break

            elif response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = tool_executor.execute(
                            block.name, block.input, user_id, db
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                logger.warning("Unexpected stop_reason: %s", response.stop_reason)
                sms_service.send_sms(user.phone_number, _FALLBACK_MESSAGE)
                break

        else:
            # Loop exhausted without end_turn
            sms_service.send_sms(user.phone_number, _FALLBACK_MESSAGE)

    except Exception:
        logger.exception("Error in orchestrator.handle_message for user_id=%s", user_id)
        if user_phone:
            try:
                sms_service.send_sms(user_phone, _FALLBACK_MESSAGE)
            except Exception:
                logger.exception("Failed to send fallback SMS for user_id=%s", user_id)

    finally:
        if _owns_db:
            db.close()
