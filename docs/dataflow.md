# Dataflow

All user-initiated flows start with an inbound SMS arriving at Twilio and end with an outbound SMS response. The timeout flow is triggered by a Railway cron job instead.

---

## 1. Happy Path — Adding Items

1. User sends SMS: `"add milk and eggs"`
2. Twilio POSTs to `/webhook/sms` with `From`, `Body`, `MessageSid`
3. Webhook validates Twilio signature (skipped when `ENVIRONMENT=development`)
4. Webhook queries `messages` table for `twilio_sid = MessageSid` — not found, continue
5. Webhook queries `users` table for `phone_number = From` — found (Chris or Donna)
6. Webhook writes inbound `Message` record to DB
7. Webhook enqueues `BackgroundTask: orchestrator.handle_message(user_id, "add milk and eggs")`
8. Webhook returns `<Response/>` (HTTP 200) to Twilio immediately
9. Background task starts: `orchestrator.handle_message()`
10. `context_builder.build_system_prompt(user, db)` queries DB: active list items, brand prefs, pending confirmations, last 10 messages; returns system prompt string
11. Orchestrator selects model by inspecting the system prompt string for `"pending"` and `"brand"` keywords — no matches → Haiku (`claude-haiku-4-5-20251001`)
12. Orchestrator calls `anthropic.messages.create()` with system prompt + user message + 11 tool schemas
13. Claude responds: `stop_reason="tool_use"`, calls `parse_items(text="add milk and eggs")`
14. `tool_executor.execute("parse_items", ...)` returns `{"status": "ok", "message": "Text received..."}`
15. Orchestrator appends tool result to messages list; calls `anthropic.messages.create()` again
16. Claude calls `check_duplicates(items=[{"name": "milk"}, {"name": "eggs"}])`
17. `tool_executor` → `duplicate_service.check_duplicates()` → fuzzy-matches against active list items using `rapidfuzz.token_set_ratio` → both score below threshold (default 85) → both clear
18. Returns `{"clear": [{"name": "milk"}, {"name": "eggs"}], "possible_duplicates": []}`
19. Orchestrator appends result; calls Claude again
20. Claude calls `add_items(items=[{"name": "milk", "quantity": 1, "unit": null, ...}, {"name": "eggs", "quantity": 1, ...}])`
21. `tool_executor` → `item_service.add_items()` → creates 2 `Item` records (status=ACTIVE); auto-applies any stored brand preferences where `brand_pref` was not provided
22. Returns `{"added": [{"id": 1, "name": "milk"}, {"id": 2, "name": "eggs"}], "count": 2}`
23. Orchestrator appends result; calls Claude again
24. Claude responds: `stop_reason="end_turn"`, text: `"Got it! Added milk and eggs to your list."`
25. Orchestrator extracts text from response; calls `sms_service.send_sms(user.phone_number, text)`
26. Orchestrator logs outbound `Message` record (with `twilio_sid=None`) to DB
27. User receives SMS: `"Got it! Added milk and eggs to your list."`

---

## 2. Duplicate Detection Path

Steps 1–16 are identical to the happy path. The divergence occurs when `check_duplicates` returns a match:

17. `duplicate_service.check_duplicates()` → "milk" scores 100 against existing "milk" (id=5) — at or above threshold (85)
18. Returns `{"clear": [], "possible_duplicates": [{"new_item": {"name": "milk"}, "existing_item_id": 5, "existing_item_name": "milk", "score": 100}]}`
19. Orchestrator appends result; calls Claude
20. Claude calls `hold_pending(item={"name": "milk", "quantity": 1, ...}, existing_item_id=5)`
21. `tool_executor` → `item_service.hold_pending()` → creates `Item` (status=PENDING) + `PendingConfirmation` row (expires 24h from now) linking new item to existing item id=5
22. Returns `{"status": "pending", "pending_item_id": 6, "name": "milk"}`
23. Claude responds: `stop_reason="end_turn"`: `"Milk might already be on the list — want me to add it anyway, or skip it?"`
24. User receives confirmation prompt via SMS
25. User replies: `"yes add it"`
26. New inbound webhook flow starts from step 1
27. `context_builder` includes pending confirmation in system prompt; system prompt now contains `"pending"` → model upgrades to Sonnet
28. Claude resolves confirmation by calling `add_items()` to promote the pending item to ACTIVE status

---

## 3. Send List Path

1. User sends SMS: `"send the list to chris"`
2. Steps 1–12 same as happy path
3. Claude calls `send_list(shopper_phone="+1XXXXXXXXXX")`
4. `tool_executor` → `list_service.get_list(db)` to fetch list data (called BEFORE status transition)
5. Guard check: if list has no items, returns `{"error": "No items on the list to send."}`
6. `list_service.send_list(db)` → transitions active list `ACTIVE → SENT`, sets `sent_at` timestamp
7. `formatting.format_list(list_data)` → produces formatted text: date header, categories (ALL CAPS in canonical order), items with quantity/unit/brand; PENDING items marked with `*`
8. `formatting.split_sms(text, max_chars=1500)`:
   - If text ≤ 1500 chars: single chunk, no prefix
   - If larger: splits at category boundaries with `(1/N)` prefixes; footer (`"* = pending confirmation\nReply DONE when finished."`) on last chunk only
9. `sms_service.send_sms()` called once per chunk — SMS delivered to shopper's phone
10. Returns `{"status": "sent", "list_id": 1, "sent_at": "2026-04-21T..."}`
11. Claude responds: `stop_reason="end_turn"`: `"List sent to Chris!"`
12. Orchestrator sends confirmation SMS to the requesting user

---

## 4. Archive Path

1. User sends SMS: `"done"` or `"we're finished shopping"`
2. Steps 1–12 same as happy path
3. Claude calls `archive_list()`
4. `tool_executor` → `list_service.archive_list(db)` → transitions `SENT → ARCHIVED`, sets `archived_at`; immediately creates a new empty `ShoppingList` with status `ACTIVE`
5. Returns `{"status": "archived", "archived_list_id": 1, "archived_at": "2026-04-21T..."}`
6. Claude responds: `stop_reason="end_turn"`: `"Shopping trip complete! Started a fresh list."`
7. User receives confirmation SMS

---

## 5. Timeout Check Path

1. Railway cron fires every 30 minutes: `curl -X POST .../tasks/timeout-check -H 'X-Cron-Secret: ...'`
2. `routers/tasks.py` validates `X-Cron-Secret` header — returns HTTP 403 if missing or incorrect
3. Calls `run_timeout_check(db)`
4. Queries DB: all `ShoppingList` records with `status=SENT` and `sent_at < (now - 8 hours)`
5. For each timed-out list:
   a. Calls `message_service.has_timeout_prompt_been_sent(list.sent_at, list.id, db)` — searches message history for `"Did you finish"` in messages logged after `sent_at`
   b. If already sent: skip (idempotency)
   c. If not sent: calls `sms_service.send_sms()` to all users: `"Did you finish your shopping trip? Reply DONE to archive the list or CANCEL to keep it active."`
   d. Logs outbound `Message` records with `twilio_sid=None` for each user
6. Returns `{"status": "ok", "checked": N}`

---

## 6. Error Paths

### Unknown phone number
- Step 5 of the happy path: `users` query returns no result for `From` phone number
- Webhook calls `sms_service.send_error_sms(From)` — sends a rejection SMS
- Webhook returns HTTP 200 (no further processing; no background task enqueued)

### Tool failure mid-loop
- A tool handler raises an exception inside `tool_executor.execute()`
- The exception is caught; handler returns `{"error": "exception message"}`
- Orchestrator appends the error result to messages and continues the loop
- Claude sees the error and can retry the tool, skip the step, or inform the user

### Loop exhaustion (10 iterations without end_turn)
- The `for` loop in the orchestrator completes all 10 iterations without a `break`
- Python's `for...else` clause triggers: sends fallback SMS `"Sorry, I had trouble processing that. Please try again."`
- No outbound message is logged in this case

### Claude API exception
- `anthropic.messages.create()` raises any exception
- Orchestrator's outer `try/except` catches it
- Calls `sms_service.send_sms()` with fallback message if `user_phone` is cached
- Logs the exception via `logger.exception()`
