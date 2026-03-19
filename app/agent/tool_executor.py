"""
Tool executor — dispatch tool calls to the appropriate service functions.

Each handler receives (tool_input: dict, user_id: int, db: Session) and
returns a result that can be serialised to a string for the Anthropic API.

Phase 2 fully implements: parse_items, add_items.
All other tools are stubs that return a placeholder (Phase 3 will fill them in).
"""
import json
from sqlalchemy.orm import Session

from app.services import item_service


# ---------------------------------------------------------------------------
# Fully implemented handlers (Phase 2)
# ---------------------------------------------------------------------------

def _handle_parse_items(tool_input: dict, user_id: int, db: Session):
    """
    Parse items from text.

    In Phase 2 the heavy lifting is done by Claude itself; this tool simply
    echoes back the text so Claude can produce structured items on the next
    iteration.  Phase 3 will add a real NLP pipeline if needed.
    """
    # Return a clear directive so Claude knows to call add_items next.
    return {
        "status": "ok",
        "message": "Text received. Please call add_items with the items you've identified from the text.",
    }


def _handle_add_items(tool_input: dict, user_id: int, db: Session):
    """Write items to the DB via item_service."""
    items = tool_input.get("items", [])
    list_id = tool_input.get("list_id")
    created = item_service.add_items(items=items, list_id=list_id, user_id=user_id, db=db)
    return {
        "added": [{"id": i.id, "name": i.name} for i in created],
        "count": len(created),
    }


# ---------------------------------------------------------------------------
# Stub handlers (Phase 3)
# ---------------------------------------------------------------------------

def _stub(name: str):
    def handler(tool_input: dict, user_id: int, db: Session):
        return {"status": "not_implemented", "tool": name}
    handler.__name__ = f"_handle_{name}"
    return handler


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict = {
    "parse_items": _handle_parse_items,
    "add_items": _handle_add_items,
    "check_duplicates": _stub("check_duplicates"),
    "hold_pending": _stub("hold_pending"),
    "lookup_brand_preference": _stub("lookup_brand_preference"),
    "save_brand_preference": _stub("save_brand_preference"),
    "get_list": _stub("get_list"),
    "send_list": _stub("send_list"),
    "archive_list": _stub("archive_list"),
    "override_category": _stub("override_category"),
    "set_list_status": _stub("set_list_status"),
}


def execute(tool_name: str, tool_input: dict, user_id: int, db: Session) -> str:
    """Execute a named tool and return the result as a JSON string."""
    handler = _DISPATCH.get(tool_name)
    if handler is None:
        result = {"error": f"Unknown tool: {tool_name}"}
    else:
        result = handler(tool_input, user_id, db)
    return json.dumps(result)
