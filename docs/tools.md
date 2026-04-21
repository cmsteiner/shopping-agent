# Claude Tool-Use Loop

## Loop Mechanics

The tool-use loop runs inside `orchestrator.handle_message()` in `app/agent/orchestrator.py`.

**Setup:**
1. `context_builder.build_system_prompt(user, db)` queries the DB and returns the full system prompt string: current active list items grouped by category, all brand preferences, pending confirmations for this user, and the last 10 messages in chronological order
2. Model is selected (see Model Selection below)
3. Messages list is initialized: `[{"role": "user", "content": body}]`

**Loop (max 10 iterations):**

```python
for _ in range(10):
    response = anthropic.messages.create(
        model=model,
        system=system_prompt,
        tools=TOOLS,          # from tool_definitions.py
        messages=messages,
        max_tokens=1024,
    )

    if response.stop_reason == "end_turn":
        # Extract text content, send via SMS, log outbound message, break

    elif response.stop_reason == "tool_use":
        # For each tool_use block in response.content:
        #   result = tool_executor.execute(tool_name, tool_input, user_id, db)
        #   Append assistant message + tool_result (as str(result)) to messages
        # Continue loop

    else:
        # Unexpected stop reason: send fallback SMS, break
else:
    # for...else: loop completed all 10 iterations without break
    # Send fallback SMS (no outbound message logged)
```

**Stop reason handling:**
- `end_turn`: extract text, send SMS, log outbound `Message` record, break
- `tool_use`: execute tools, append results, continue
- Other: send fallback SMS, break (no log)
- Loop exhaustion: `for...else` clause sends fallback SMS (no log)

**Exception handling:** The entire loop body is wrapped in a top-level try/except. Any unhandled exception logs the error and sends a fallback SMS if `user_phone` is cached.

---

## Model Selection

```python
def _select_model(system_prompt: str) -> str:
    prompt_lower = system_prompt.lower()
    use_sonnet = (
        "pending" in prompt_lower
        or ("brand" in prompt_lower and prompt_lower.count("-") > 2)
    )
    return settings.sonnet_model if use_sonnet else settings.haiku_model
```

The selection is a string search on the **already-assembled** system prompt — no additional DB queries are made at decision time.

- **Haiku** (`claude-haiku-4-5-20251001`): default
- **Sonnet** (`claude-sonnet-4-6`): used when:
  - System prompt contains `"pending"` — indicates an unresolved pending confirmation is in context
  - System prompt contains `"brand"` AND has more than two dash characters — proxy for a list with multiple brand-prefixed items

---

## Tool Dispatch

`tool_executor.execute(tool_name, tool_input, user_id, db)` maps `tool_name` to a `_handle_<name>()` function.

Every handler:
- Calls the appropriate service function(s)
- Returns a plain dict
- Catches all exceptions and returns `{"error": str(e)}` instead of raising

Tool results are converted to strings before being added to the messages list: `"content": str(result)`. Claude receives the stringified representation.

A tool failure never crashes the conversation loop — Claude sees the error string and can recover.

---

## Tools

### `parse_items`

**Purpose:** Signal to Claude that it should parse the user's natural language input into structured item data. Claude performs the actual parsing; this tool provides an acknowledgment and instructs Claude to proceed to `add_items`.

**Input:**
```json
{"text": "add milk and eggs"}
```

**Service call:** None

**Returns:**
```json
{
  "status": "ok",
  "message": "Text received. Please call add_items with the items you've identified from the text."
}
```

---

### `check_duplicates`

**Purpose:** Fuzzy-match a list of new items against items currently on the ACTIVE list, to detect potential duplicates before adding.

**Input:**
```json
{"items": [{"name": "milk"}, {"name": "eggs"}]}
```

**Service call:** `duplicate_service.check_duplicates(items, db)`

Uses `rapidfuzz.token_set_ratio`. Threshold is `settings.duplicate_threshold` (default: 85). Items scoring below the threshold are "clear"; at or above are "possible_duplicates".

**Returns:**
```json
{
  "clear": [{"name": "eggs"}],
  "possible_duplicates": [
    {
      "new_item": {"name": "milk"},
      "existing_item_id": 5,
      "existing_item_name": "milk",
      "score": 100
    }
  ]
}
```

---

### `add_items`

**Purpose:** Add one or more items to the current ACTIVE list.

**Input:**
```json
{
  "items": [
    {"name": "milk", "quantity": 1, "unit": null, "brand_pref": null, "category": null}
  ],
  "list_id": null
}
```

**Service call:** `item_service.add_items(items, list_id, user_id, db)`

If `brand_pref` is not provided for an item, the service automatically looks up and applies any stored brand preference for that item name.

**Returns:**
```json
{"added": [{"id": 1, "name": "milk"}], "count": 1}
```

---

### `hold_pending`

**Purpose:** Create a PENDING item (possible duplicate) and link it to the existing item via a `PendingConfirmation` record.

**Input:**
```json
{"item": {"name": "milk", "quantity": 1, "unit": null}, "existing_item_id": 5}
```

**Service call:** `item_service.hold_pending(item_dict, existing_item_id, triggered_by, db)`

Creates an `Item` with `status=PENDING` and a `PendingConfirmation` linking it to the existing item. Confirmation expires 24 hours from creation (informational only — not enforced).

**Returns:**
```json
{"status": "pending", "pending_item_id": 6, "name": "milk"}
```

---

### `lookup_brand_preference`

**Purpose:** Look up a stored brand preference for a specific item name.

**Input:**
```json
{"item_name": "milk"}
```

**Service call:** `brand_service.get_brand_preference(item_name, db)`

Lookup is case-insensitive.

**Returns (found):**
```json
{"found": true, "item_name": "milk", "brand": "Organic Valley"}
```

**Returns (not found):**
```json
{"found": false, "item_name": "milk"}
```

---

### `save_brand_preference`

**Purpose:** Store or update a brand preference for an item name. Upserts — creates a new record or updates the existing one.

**Input:**
```json
{"item_name": "milk", "brand": "Organic Valley"}
```

**Service call:** `brand_service.save_brand_preference(item_name, brand, user_id, db)`

Brand preferences are global (shared by all users). Last write wins.

**Returns:**
```json
{"status": "saved", "item_name": "milk", "brand": "Organic Valley"}
```

---

### `get_list`

**Purpose:** Retrieve the current shopping list grouped by category.

**Input:** None (empty object `{}`)

**Service call:** `list_service.get_list(db)`

Returns the ACTIVE list if one exists; falls back to the SENT list. PENDING items are included with a `"pending": true` annotation.

**Returns:**
```json
{
  "list_id": 1,
  "status": "ACTIVE",
  "items_by_category": {
    "DAIRY": [
      {"id": 1, "name": "milk", "quantity": 1, "unit": null, "brand_pref": "Organic Valley", "status": "ACTIVE"}
    ]
  }
}
```

---

### `send_list`

**Purpose:** Fetch and format the list, transition it to SENT status, and deliver it via SMS to the specified shopper.

**Input:**
```json
{"shopper_phone": "+15551234567"}
```

**Service calls (in order):**
1. `list_service.get_list(db)` — fetch list data **before** status transition
2. Guard: if no items, return `{"error": "No items on the list to send."}`
3. `list_service.send_list(db)` — transitions ACTIVE → SENT, sets `sent_at`
4. `formatting.format_list(list_data)` — produces formatted SMS text
5. `formatting.split_sms(text)` — splits into chunks if text exceeds `settings.max_sms_chars` (default 1500)
6. `sms_service.send_sms(shopper_phone, chunk)` — called once per chunk

**Returns:**
```json
{"status": "sent", "list_id": 1, "sent_at": "2026-04-21T14:00:00"}
```

**Note:** SMS is sent as a side effect inside this tool call. If the tool succeeds but the Claude loop subsequently fails, the SMS has already been delivered.

---

### `archive_list`

**Purpose:** Transition the current SENT list to ARCHIVED and create a new empty ACTIVE list.

**Input:** None (empty object `{}`)

**Service call:** `list_service.archive_list(db)`

**Returns:**
```json
{"status": "archived", "archived_list_id": 1, "archived_at": "2026-04-21T15:00:00"}
```

**Constraint:** Raises `ValueError("No SENT list found. Can only archive a SENT list.")` if no SENT list exists. Not DB-enforced — caught by `tool_executor` and returned as `{"error": "..."}`.

---

### `override_category`

**Purpose:** Manually reassign an item to a different category.

**Input:**
```json
{"item_id": 3, "category": "dairy"}
```

**Service call:** `item_service.override_category(item_id, category, db)`

The category string is normalized via `utils.category.normalize_category()` before saving. Valid canonical categories: PRODUCE, DAIRY, MEAT, SEAFOOD, BAKERY, FROZEN, PANTRY, BEVERAGES, SNACKS, CLEANING, PERSONAL CARE, HOUSEHOLD, OTHER.

**Returns:**
```json
{"status": "updated", "item_id": 3, "category": "DAIRY"}
```

---

### `set_list_status`

**Purpose:** Transition the list to SENT or ARCHIVED using a target status string.

**Input:**
```json
{"list_id": 1, "status": "SENT"}
```
or
```json
{"list_id": 1, "status": "ARCHIVED"}
```

Both fields are required by the schema. The handler routes on `status` only (`list_id` is accepted but not used).

**Service calls:** Same as `send_list` (for `SENT`) or `archive_list` (for `ARCHIVED`).

**Returns:**
```json
{"status": "ok", "list_id": 1, "new_status": "SENT"}
```

**Note:** When using `set_list_status` with `"status": "SENT"`, the list is transitioned to SENT but **no SMS is sent** — unlike the `send_list` tool which sends the formatted list to a shopper. Use `send_list` when you need the SMS delivery; use `set_list_status` only for the status transition.

---

## Adding a New Tool

Four steps:

**1. Define the schema** in `app/agent/tool_definitions.py`:

```python
{
    "name": "my_new_tool",
    "description": "What this tool does and when Claude should call it.",
    "input_schema": {
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "Description of this parameter"}
        },
        "required": ["param"]
    }
}
```

**2. Add a handler** in `app/agent/tool_executor.py`:

```python
def _handle_my_new_tool(tool_input: dict, user_id: int, db: Session) -> dict:
    try:
        result = my_service.do_something(tool_input["param"], db)
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"error": str(e)}
```

**3. Wire it into the dispatch map** in `tool_executor.execute()`:

```python
"my_new_tool": _handle_my_new_tool,
```

**4. If Claude needs explicit instructions about when to call the new tool, add a note to the system prompt in `app/agent/context_builder.py`.**

---

## Known Constraints

- `archive_list` requires a SENT list to exist — not DB-enforced; Claude-instructed. Raises `ValueError` if violated; caught by `tool_executor`.
- Tool call order matters in the duplicate flow: `check_duplicates` must precede `add_items` or `hold_pending`. The system prompt instructs Claude on this ordering; there is no runtime enforcement.
- `send_list` sends SMS as a side effect inside a tool call. If the Claude loop fails after the tool succeeds, the SMS has already been delivered.
- `set_list_status` with `"status": "SENT"` transitions the list status but does NOT send the formatted list via SMS. Use the `send_list` tool for that.
