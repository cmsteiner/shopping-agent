"""
All 11 tool schemas as Anthropic tool dicts.

Each tool follows the Anthropic tools API schema:
  {"name": str, "description": str, "input_schema": {...}}
"""

TOOLS: list[dict] = [
    {
        "name": "parse_items",
        "description": (
            "Acknowledges the natural language text for item extraction. "
            "Claude should parse the items itself and proceed to call add_items "
            "with the extracted items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The raw user text to parse for grocery items.",
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "check_duplicates",
        "description": (
            "Fuzzy-match proposed items against the current active shopping list. "
            "Returns any items whose name similarity exceeds the duplicate threshold."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of parsed item objects to check.",
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "add_items",
        "description": (
            "Write confirmed items to the database and add them to the active "
            "shopping list. Returns the created item records."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "quantity": {"type": "number"},
                            "unit": {"type": "string"},
                            "brand_hint": {"type": "string"},
                            "category": {"type": "string"},
                        },
                        "required": ["name"],
                    },
                    "description": "Items to add to the shopping list.",
                },
                "list_id": {
                    "type": "integer",
                    "description": "ID of the shopping list to add items to. Optional — uses active list if omitted.",
                },
            },
            "required": ["items"],
        },
    },
    {
        "name": "hold_pending",
        "description": (
            "Stage a duplicate-flagged item as PENDING, awaiting user confirmation "
            "before it is added to the list."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item": {
                    "type": "object",
                    "description": "The parsed item to hold as PENDING.",
                },
                "existing_item_id": {
                    "type": "integer",
                    "description": "ID of the existing item it conflicts with.",
                },
            },
            "required": ["item", "existing_item_id"],
        },
    },
    {
        "name": "lookup_brand_preference",
        "description": "Query the stored brand preference for a given item name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The generic item name to look up.",
                },
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "save_brand_preference",
        "description": "Persist a user's brand preference for an item.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "The generic item name.",
                },
                "brand": {
                    "type": "string",
                    "description": "The preferred brand name.",
                },
            },
            "required": ["item_name", "brand"],
        },
    },
    {
        "name": "get_list",
        "description": (
            "Return the current shopping list grouped by category, suitable for "
            "display to the user."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "send_list",
        "description": (
            "Format the current shopping list and dispatch it as an SMS to the "
            "shopper. Sets the list status to SENT."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "shopper_phone": {
                    "type": "string",
                    "description": "Phone number of the person doing the shopping.",
                },
            },
            "required": ["shopper_phone"],
        },
    },
    {
        "name": "archive_list",
        "description": (
            "Mark the current list as DONE/ARCHIVED and reset for a new shopping "
            "trip. Returns confirmation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "override_category",
        "description": "Update the category of an existing item on the list.",
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "ID of the item to update.",
                },
                "category": {
                    "type": "string",
                    "description": "New category value.",
                },
            },
            "required": ["item_id", "category"],
        },
    },
    {
        "name": "set_list_status",
        "description": (
            "Manage shopping list status transitions: ACTIVE → SENT → ARCHIVED."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_id": {
                    "type": "integer",
                    "description": "ID of the shopping list to update.",
                },
                "status": {
                    "type": "string",
                    "enum": ["ACTIVE", "SENT", "ARCHIVED"],
                    "description": "Target status.",
                },
            },
            "required": ["list_id", "status"],
        },
    },
]
