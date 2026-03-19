"""
Tool executor — dispatch tool calls to the appropriate service functions.

Each handler receives (tool_input: dict, user_id: int, db: Session) and
returns a result that can be serialised to a string for the Anthropic API.

Phase 2 fully implements: parse_items, add_items.
Phase 3 fills in all remaining stubs.
"""
import json
from sqlalchemy.orm import Session

from app.services import item_service, sms_service
from app.services import duplicate_service, list_service, brand_service


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
# Phase 3 implementations
# ---------------------------------------------------------------------------

def _handle_check_duplicates(tool_input: dict, user_id: int, db: Session):
    """Check new items for fuzzy duplicates against the active list."""
    items = tool_input.get("items", [])
    result = duplicate_service.check_duplicates(items, db)
    return {
        "clear": result["clear"],
        "possible_duplicates": [
            {
                "new_item": new_item,
                "existing_item_id": existing.id,
                "existing_item_name": existing.name,
                "score": score,
            }
            for new_item, existing, score in result["possible_duplicates"]
        ],
    }


def _handle_hold_pending(tool_input: dict, user_id: int, db: Session):
    """Stage a duplicate-flagged item as PENDING."""
    item_dict = tool_input.get("item", {})
    existing_item_id = tool_input.get("existing_item_id")
    pending = item_service.hold_pending(
        item_dict=item_dict,
        existing_item_id=existing_item_id,
        triggered_by=user_id,
        db=db,
    )
    return {
        "status": "pending",
        "pending_item_id": pending.id,
        "name": pending.name,
    }


def _handle_lookup_brand_preference(tool_input: dict, user_id: int, db: Session):
    """Look up a stored brand preference."""
    item_name = tool_input.get("item_name", "")
    pref = brand_service.get_brand_preference(item_name, db)
    if pref is None:
        return {"found": False, "item_name": item_name}
    return {
        "found": True,
        "item_name": pref.item_name,
        "brand": pref.brand,
    }


def _handle_save_brand_preference(tool_input: dict, user_id: int, db: Session):
    """Persist a brand preference."""
    item_name = tool_input.get("item_name", "")
    brand = tool_input.get("brand", "")
    pref = brand_service.save_brand_preference(
        item_name=item_name, brand=brand, user_id=user_id, db=db
    )
    return {
        "status": "saved",
        "item_name": pref.item_name,
        "brand": pref.brand,
    }


def _handle_get_list(tool_input: dict, user_id: int, db: Session):
    """Return the current shopping list grouped by category."""
    return list_service.get_list(db)


def _handle_send_list(tool_input: dict, user_id: int, db: Session):
    """Transition ACTIVE → SENT and send formatted list SMS to shopper."""
    shopper_phone = tool_input.get("shopper_phone", "")
    updated_list = list_service.send_list(db)

    # Build a simple formatted list message
    list_data = list_service.get_list(db)
    lines = ["Shopping list:"]
    for category, items in list_data.get("items_by_category", {}).items():
        lines.append(f"\n{category}:")
        for item in items:
            qty = f"{item['quantity']} {item['unit']} " if item.get("quantity") else ""
            brand = f"({item['brand_pref']}) " if item.get("brand_pref") else ""
            lines.append(f"  - {qty}{brand}{item['name']}")

    message = "\n".join(lines)
    if shopper_phone:
        sms_service.send_sms(shopper_phone, message)

    return {
        "status": "sent",
        "list_id": updated_list.id,
        "sent_at": updated_list.sent_at.isoformat() if updated_list.sent_at else None,
    }


def _handle_archive_list(tool_input: dict, user_id: int, db: Session):
    """Archive the current SENT list and create a new ACTIVE list."""
    archived = list_service.archive_list(db)
    return {
        "status": "archived",
        "archived_list_id": archived.id,
        "archived_at": archived.archived_at.isoformat() if archived.archived_at else None,
    }


def _handle_override_category(tool_input: dict, user_id: int, db: Session):
    """Update an item's category."""
    item_id = tool_input.get("item_id")
    category = tool_input.get("category", "")
    updated = item_service.override_category(item_id=item_id, category=category, db=db)
    return {
        "status": "updated",
        "item_id": updated.id,
        "category": updated.category,
    }


def _handle_set_list_status(tool_input: dict, user_id: int, db: Session):
    """Manage list status transitions."""
    target_status = tool_input.get("status", "")

    if target_status == "SENT":
        updated = list_service.send_list(db)
    elif target_status == "ARCHIVED":
        updated = list_service.archive_list(db)
    else:
        return {"error": f"Unsupported target status: {target_status}"}

    return {
        "status": "ok",
        "list_id": updated.id,
        "new_status": updated.status.value,
    }


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict = {
    "parse_items": _handle_parse_items,
    "add_items": _handle_add_items,
    "check_duplicates": _handle_check_duplicates,
    "hold_pending": _handle_hold_pending,
    "lookup_brand_preference": _handle_lookup_brand_preference,
    "save_brand_preference": _handle_save_brand_preference,
    "get_list": _handle_get_list,
    "send_list": _handle_send_list,
    "archive_list": _handle_archive_list,
    "override_category": _handle_override_category,
    "set_list_status": _handle_set_list_status,
}


def execute(tool_name: str, tool_input: dict, user_id: int, db: Session) -> str:
    """Execute a named tool and return the result as a JSON string."""
    handler = _DISPATCH.get(tool_name)
    if handler is None:
        result = {"error": f"Unknown tool: {tool_name}"}
    else:
        try:
            result = handler(tool_input, user_id, db)
        except ValueError as exc:
            result = {"error": str(exc)}
    return json.dumps(result)
