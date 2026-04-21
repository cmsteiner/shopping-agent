# Architecture Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write six documentation files covering architecture, dataflow, database schema, Claude tool-use, testing infrastructure, and AI-agent context for the shopping-agent codebase.

**Architecture:** Each file is independent and targets a specific audience concern. `CLAUDE.md` is the lean AI-facing entry point; the `docs/` files are the authoritative human-readable reference. No code changes — documentation only.

**Tech Stack:** Markdown, SQLAlchemy/SQLite, FastAPI, Twilio, Anthropic Claude API

---

## File Map

| File | Status |
|------|--------|
| `CLAUDE.md` | Create |
| `docs/architecture.md` | Create |
| `docs/dataflow.md` | Create |
| `docs/database.md` | Create |
| `docs/tools.md` | Create |
| `docs/testing.md` | Create |

---

## Task 1: `CLAUDE.md`

**Files:**
- Create: `CLAUDE.md`

- [ ] **Step 1: Write the file**

Create `CLAUDE.md` at the repo root with this exact content:

```markdown
# Shopping Agent

SMS-driven household shopping list manager for two users (Chris and Donna). Users send natural language text messages via Twilio; the app processes them through a Claude tool-use loop and responds via SMS.

## Tech Stack

- **Runtime**: Python 3.11+, FastAPI, uvicorn
- **Database**: SQLAlchemy ORM + SQLite (Railway Volume at `/data/shopping.db`)
- **SMS**: Twilio (inbound webhook + outbound send)
- **AI**: Anthropic Claude API (tool-use loop)
- **Migrations**: Alembic
- **Deployment**: Railway (web service + cron job)

## Entry Points

| Endpoint | Purpose |
|----------|---------|
| `POST /webhook/sms` | Inbound Twilio SMS webhook |
| `POST /tasks/timeout-check` | Railway cron — checks for timed-out shopping trips |
| `GET /health` | Railway liveness check |

## Critical Constraint

**The webhook handler must return HTTP 200 immediately.** All Claude API calls happen in a FastAPI `BackgroundTask`. If the webhook blocks waiting for Claude, Twilio will retry the request — causing duplicate processing.

## Layer Map

```
routers/          ← HTTP request handling, signature validation, idempotency
  └─ agent/       ← Claude tool-use loop
      ├─ orchestrator.py       (loop driver)
      ├─ context_builder.py    (system prompt assembly)
      ├─ tool_definitions.py   (Anthropic tool schemas)
      └─ tool_executor.py      (tool dispatch → services)
  └─ services/    ← Business logic, DB mutations
  └─ models/      ← SQLAlchemy ORM models
  └─ utils/       ← SMS formatting, category normalization
```

## Extension Points

**Adding a new tool:**
1. Add schema to `app/agent/tool_definitions.py`
2. Add handler `_handle_<name>()` to `app/agent/tool_executor.py`
3. Add service logic to `app/services/` if needed
4. Update the system prompt in `app/agent/orchestrator.py` to instruct Claude when to use it

**Adding a new delivery channel (web UI, voice, etc.):**
1. Add a new router in `app/routers/`
2. Parse the incoming request and call `orchestrator.handle_message(user_id, body, db)`
3. Do NOT call Claude synchronously — enqueue via FastAPI `BackgroundTask` or async queue

## What NOT to Do

- Do not call `anthropic.Anthropic().messages.create()` inside a request handler
- Do not add list state transitions (`ACTIVE → SENT → ARCHIVED`) outside `app/services/list_service.py`
- Do not add brand preference upsert logic outside `app/services/brand_service.py`

## Full Documentation

- [Architecture](docs/architecture.md) — layers, components, key design decisions
- [Dataflow](docs/dataflow.md) — all message paths end-to-end
- [Database](docs/database.md) — schema, state machines, constraints
- [Tools](docs/tools.md) — Claude tool-use loop mechanics, all 11 tools, extension guide
- [Testing](docs/testing.md) — test fixtures, mock strategy, test file inventory
```

- [ ] **Step 2: Verify against spec**

Check that `CLAUDE.md` covers every item listed in the spec section for this file:
- [ ] One-sentence app summary; two users; SMS-driven
- [ ] Tech stack (FastAPI, SQLAlchemy/SQLite, Twilio, Anthropic, Railway)
- [ ] Entry points (`/webhook/sms`, `/tasks/timeout-check`, `/health`)
- [ ] Critical constraint: background task pattern
- [ ] Layer map
- [ ] Extension points: adding a tool; adding a channel
- [ ] Pointers to `docs/`
- [ ] What NOT to do

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add CLAUDE.md with architecture orientation for AI agents"
```

---

## Task 2: `docs/architecture.md`

**Files:**
- Create: `docs/architecture.md`

- [ ] **Step 1: Create the docs directory and write the file**

```bash
mkdir -p docs
```

Create `docs/architecture.md` with this exact content:

```markdown
# Architecture

## What This Is

A household shopping list manager operated entirely via SMS. Two users — Chris and Donna — can add items, check the list, and send it to the shopper using natural language text messages. The system uses Claude's tool-use API to parse and execute those messages.

## Users & Deployment

- **Users**: Chris and Donna (phone numbers in env vars; seeded into the DB on application startup)
- **Deployment**: Railway web service + cron job
- **Database**: SQLite file on a Railway Volume (`/data/shopping.db`)
- **SMS provider**: Twilio

## Layer Diagram

```
┌─────────────────────────────────────────────────┐
│                   HTTP Layer                    │
│   routers/health.py                             │
│   routers/webhook.py     routers/tasks.py       │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│                  Agent Layer                    │
│   orchestrator.py    (tool-use loop)            │
│   context_builder.py (system prompt assembly)   │
│   tool_definitions.py (Anthropic schemas)       │
│   tool_executor.py   (tool dispatch)            │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│                Services Layer                   │
│   item_service      list_service                │
│   brand_service     duplicate_service           │
│   message_service   sms_service                 │
│   user_service                                  │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│              Models / Database                  │
│   User   ShoppingList   Item                    │
│   BrandPreference   Message                     │
│   PendingConfirmation                           │
└─────────────────────────┬───────────────────────┘
                          │
┌─────────────────────────▼───────────────────────┐
│              External Services                  │
│   Twilio (SMS)     Anthropic (Claude API)       │
└─────────────────────────────────────────────────┘
```

## Component Responsibilities

### `app/routers/webhook.py`
Owns inbound SMS handling: Twilio signature validation, idempotency check via MessageSid, user lookup by phone number, inbound message logging, and background task dispatch. Does **not** own any business logic — it hands off to the agent layer immediately after logging.

### `app/routers/tasks.py`
Owns the cron endpoint for timeout checks. Validates the `X-Cron-Secret` header and delegates entirely to `run_timeout_check()`. Does **not** own scheduling or timeout logic.

### `app/agent/orchestrator.py`
Owns the Claude tool-use loop: assembles context, selects model, drives the while loop, handles stop reasons, and sends the final SMS response. Does **not** own list or item business logic — that lives in services.

### `app/agent/context_builder.py`
Owns system prompt assembly. Queries the DB for current list items, brand preferences, pending confirmations, and recent message history (last 10 messages). Returns a single string. Makes **no** mutations.

### `app/agent/tool_definitions.py`
Owns the Anthropic-format JSON schemas for all 11 tools. No logic — pure schema definitions.

### `app/agent/tool_executor.py`
Owns the mapping from tool name to handler function. Each handler calls the appropriate service and returns a result dict to Claude. Does **not** own service logic — only dispatch and result formatting. Exceptions are caught and returned as `{"error": "..."}` dicts so the loop continues rather than crashing.

### `app/services/`
Each service owns one domain of DB mutation:
- `item_service`: creating, updating, and holding items
- `list_service`: list state transitions (ACTIVE → SENT → ARCHIVED) and retrieval
- `brand_service`: brand preference upsert and lookup
- `duplicate_service`: fuzzy-match new items against the active list
- `message_service`: logging inbound/outbound messages and idempotency checks
- `sms_service`: Twilio client wrapper — the only place that calls Twilio's REST API
- `user_service`: user lookup by phone number or ID

### `app/utils/formatting.py`
Owns SMS text formatting (`format_list`) and multi-chunk splitting (`split_sms`). Makes no DB access and contains no business logic.

### `app/utils/category.py`
Owns the canonical ordered category list (13 categories) and the `normalize_category()` function. Used by formatting and item service.

## Key Design Decisions

### Background Task Pattern
The webhook handler enqueues `orchestrator.handle_message()` as a FastAPI `BackgroundTask` and returns `<Response/>` (HTTP 200) to Twilio immediately. This is required because the Claude API call can take several seconds, and Twilio will retry the webhook if it does not receive a response within ~15 seconds.

### Idempotency via MessageSid
Every inbound Twilio message has a unique `MessageSid`. The webhook handler checks the `messages` table for a matching `twilio_sid` before processing. If found, it returns HTTP 200 without reprocessing. This safely handles Twilio retries without creating duplicate items.

### Model Selection: Haiku vs Sonnet
By default the loop uses `claude-haiku-4-5-20251001` (fast, cheap). It upgrades to `claude-sonnet-4-6` when the context includes pending confirmations, or when the user message contains multiple items and at least one stored brand preference exists. These cases require more reasoning.

### Tool Exception Isolation
Every handler in `tool_executor.py` wraps its logic in try/except and returns `{"error": "..."}` on failure rather than raising. This means a single tool failure does not crash the conversation — Claude sees the error and can recover or inform the user.

## Intentional Absences

These are **not** missing features — they are deliberate scope decisions for this household use case:

- **No authentication**: the system trusts that only known phone numbers will text it; access is controlled by Twilio number configuration
- **No multi-household support**: one global shopping list, two hardcoded users
- **No outbound SID tracking**: `sms_service.send_sms()` returns the Twilio SID but it is not persisted; outbound `Message` records have `twilio_sid=None`
- **No expired PendingConfirmation cleanup**: `expires_at` is informational; no background job removes stale rows
```

- [ ] **Step 2: Verify against spec**

Check that `docs/architecture.md` covers every item listed in the spec:
- [ ] Purpose, users, deployment context
- [ ] Text layer diagram (5 layers)
- [ ] Component responsibilities for each major component, including what each does NOT own
- [ ] All 4 key design decisions with reasons
- [ ] All 4 intentional absences

- [ ] **Step 3: Commit**

```bash
git add docs/architecture.md
git commit -m "docs: add architecture overview with layer diagram and design decisions"
```

---

## Task 3: `docs/dataflow.md`

**Files:**
- Create: `docs/dataflow.md`

- [ ] **Step 1: Write the file**

Create `docs/dataflow.md` with this exact content:

```markdown
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
11. Orchestrator selects model: no pending items, single-item message → Haiku (`claude-haiku-4-5-20251001`)
12. Orchestrator calls `anthropic.messages.create()` with system prompt + user message + 11 tool schemas
13. Claude responds: `stop_reason="tool_use"`, calls `parse_items(text="add milk and eggs")`
14. `tool_executor.execute("parse_items", ...)` returns `{"status": "ok"}`
15. Orchestrator appends tool result to messages list; calls `anthropic.messages.create()` again
16. Claude calls `check_duplicates(items=[{"name": "milk"}, {"name": "eggs"}])`
17. `tool_executor` → `duplicate_service.check_duplicates()` → fuzzy-matches against active list items → both score below 85 threshold → both clear
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
27. `context_builder` includes pending confirmation in system prompt
28. Claude resolves confirmation by calling `add_items()` to promote the pending item to ACTIVE status

---

## 3. Send List Path

1. User sends SMS: `"send the list to chris"`
2. Steps 1–12 same as happy path
3. Claude calls `send_list(shopper_phone="+1XXXXXXXXXX")`
4. `tool_executor` → `list_service.send_list(db)` → transitions active list `ACTIVE → SENT`, sets `sent_at` timestamp
5. `list_service.get_list(db)` → returns items grouped by category
6. `formatting.format_list(list_data)` → produces formatted text: date header, categories (ALL CAPS in canonical order), items with quantity/unit/brand; PENDING items marked with `*`
7. `formatting.split_sms(text, max_chars=1500)`:
   - If text ≤ 1500 chars: single chunk, no prefix
   - If larger: splits at category boundaries with `(1/N)` prefixes; footer (`"* = pending confirmation\nReply DONE when finished."`) on last chunk only
8. `sms_service.send_sms()` called once per chunk — SMS delivered to shopper's phone
9. Returns `{"status": "sent", "list_id": 1, "sent_at": "2026-04-21T..."}`
10. Claude responds: `stop_reason="end_turn"`: `"List sent to Chris!"`
11. Orchestrator sends confirmation SMS to the requesting user

---

## 4. Archive Path

1. User sends SMS: `"done"` or `"we're finished shopping"`
2. Steps 1–12 same as happy path
3. Claude calls `archive_list()`
4. `tool_executor` → `list_service.archive_list(db)` → transitions `SENT → ARCHIVED`, sets `archived_at`; immediately creates a new empty `ShoppingList` with status `ACTIVE`
5. Returns `{"status": "archived", "list_id": 1, "new_list_id": 2}`
6. Claude responds: `stop_reason="end_turn"`: `"Shopping trip complete! Started a fresh list."`
7. User receives confirmation SMS

---

## 5. Timeout Check Path

1. Railway cron fires every 30 minutes: `curl -X POST .../tasks/timeout-check -H 'X-Cron-Secret: ...'`
2. `routers/tasks.py` validates `X-Cron-Secret` header — returns HTTP 403 if missing or incorrect
3. Calls `run_timeout_check(db)`
4. Queries DB: all `ShoppingList` records with `status=SENT` and `sent_at < (now - 8 hours)`
5. For each timed-out list:
   a. Calls `message_service.has_timeout_prompt_been_sent(list.sent_at, list.id, db)` — searches message history for `"Did you finish"` logged after `sent_at`
   b. If already sent: skip (idempotency)
   c. If not sent: calls `sms_service.send_sms()` to all users: `"Did you finish your shopping trip? Reply DONE to archive the list or CANCEL to keep it active."`
   d. Logs outbound `Message` records with `twilio_sid=None` for each user
6. Returns `{"status": "ok", "checked": N}`

---

## 6. Error Paths

### Unknown phone number
- Step 5 of the happy path: `users` query returns no result for `From` phone number
- Webhook calls `sms_service.send_error_sms(From)` — sends a rejection SMS
- Webhook returns HTTP 200 (no further processing; no background task)

### Tool failure mid-loop
- A tool handler raises an exception inside `tool_executor.execute()`
- The exception is caught; handler returns `{"error": "exception message"}`
- Orchestrator appends the error result to messages and continues the loop
- Claude sees the error and can retry the tool, skip the step, or inform the user

### Loop exhaustion (10 iterations without end_turn)
- Orchestrator exits the while loop after 10 iterations
- Calls `sms_service.send_sms()` with fallback: `"Sorry, I had trouble processing that. Please try again."`
- Logs the fallback as an outbound message

### Claude API exception
- `anthropic.messages.create()` raises any exception
- Orchestrator's outer try/except catches it
- Calls `sms_service.send_sms()` with fallback message if possible
- Logs the error
```

- [ ] **Step 2: Verify against spec**

Check that `docs/dataflow.md` covers every path listed in the spec:
- [ ] Happy path — add items (numbered steps)
- [ ] Duplicate detection path
- [ ] Send list path
- [ ] Archive path
- [ ] Timeout check path
- [ ] All 4 error paths: unknown phone, tool failure, loop exhaustion, Claude API exception

- [ ] **Step 3: Commit**

```bash
git add docs/dataflow.md
git commit -m "docs: add end-to-end dataflow documentation for all message paths"
```

---

## Task 4: `docs/database.md`

**Files:**
- Create: `docs/database.md`

- [ ] **Step 1: Write the file**

Create `docs/database.md` with this exact content:

```markdown
# Database

SQLite in production (Railway Volume at `/data/shopping.db`). In-memory SQLite for tests. Schema migrations managed by Alembic (`alembic/`).

---

## Tables

### `users`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| name | VARCHAR | NOT NULL |
| phone_number | VARCHAR | NOT NULL, UNIQUE |

Seeded on application startup (not via Alembic migration) with Chris and Donna, using phone numbers from `settings.chris_phone` and `settings.donna_phone`. Seeding is idempotent — it skips records that already exist.

---

### `shopping_lists`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| status | VARCHAR | NOT NULL (enum: ACTIVE, SENT, ARCHIVED) |
| sent_at | DATETIME | nullable |
| archived_at | DATETIME | nullable |
| created_at | DATETIME | NOT NULL, default=now |

There is always exactly one ACTIVE list at any given time. A new ACTIVE list is created automatically when the current one is archived.

---

### `items`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| list_id | INTEGER | FK → shopping_lists.id, NOT NULL |
| name | VARCHAR | NOT NULL |
| quantity | FLOAT | nullable |
| unit | VARCHAR | nullable |
| brand_pref | VARCHAR | nullable |
| category | VARCHAR | nullable |
| status | VARCHAR | NOT NULL (enum: ACTIVE, PENDING) |
| added_by | INTEGER | FK → users.id, nullable |
| created_at | DATETIME | NOT NULL, default=now |

---

### `brand_preferences`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| item_name | VARCHAR | NOT NULL, UNIQUE |
| brand | VARCHAR | NOT NULL |
| set_by | INTEGER | FK → users.id, nullable |
| updated_at | DATETIME | NOT NULL, default=now |

One brand preference per item name (case-insensitive; stored and queried in lowercase). When a user saves a brand preference that already exists, the existing record is updated in place (last write wins). Brand preferences are global — shared by all users.

---

### `messages`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| user_id | INTEGER | FK → users.id, NOT NULL |
| direction | VARCHAR | NOT NULL (enum: INBOUND, OUTBOUND) |
| body | TEXT | NOT NULL |
| twilio_sid | VARCHAR | UNIQUE, nullable |
| created_at | DATETIME | NOT NULL, default=now |

`twilio_sid` is populated for inbound messages (from Twilio's `MessageSid` field). All outbound messages — Claude responses and system-generated timeout prompts — have `twilio_sid=NULL`. The UNIQUE constraint on `twilio_sid` is the mechanism for inbound webhook deduplication: duplicate Twilio retries are detected before any processing occurs.

---

### `pending_confirmations`

| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| item_id | INTEGER | FK → items.id, NOT NULL |
| existing_item_id | INTEGER | FK → items.id, NOT NULL |
| triggered_by | INTEGER | FK → users.id, nullable |
| expires_at | DATETIME | NOT NULL |
| created_at | DATETIME | NOT NULL, default=now |

Links a PENDING item to the existing ACTIVE item it may duplicate. `expires_at` is set to 24 hours from creation. **There is no background cleanup job** — expired rows remain in the table indefinitely. Expiry is informational only; the application does not enforce it.

---

## Relationships

```
users ─────────────────────────────── items (added_by)
  │                                     │
  │                                     │ list_id
  ├── messages (user_id)                ▼
  │                               shopping_lists
  ├── brand_preferences (set_by)
  │
  └── pending_confirmations (triggered_by)
           │
           ├── item_id ──────────────► items
           └── existing_item_id ─────► items
```

---

## State Machines

### `ShoppingList.status`

```
           list_service.send_list()            list_service.archive_list()
 ACTIVE ──────────────────────────► SENT ────────────────────────────────► ARCHIVED
   ▲                                                                            │
   │                                                                            │
   └──────────────── new ACTIVE list created by archive_list() ◄───────────────┘
```

- `ACTIVE → SENT`: `list_service.send_list()` — sets `sent_at` to current timestamp
- `SENT → ARCHIVED`: `list_service.archive_list()` — sets `archived_at`; immediately creates a new `ShoppingList(status=ACTIVE)`
- Calling `archive_list()` on an ACTIVE list raises `ValueError` (not DB-enforced; caught by `tool_executor`)

### `Item.status`

```
                item_service.hold_pending()
  ACTIVE ─────────────────────────────────► PENDING
    ▲                                           │
    │        (user confirms; Claude calls       │
    └──────── item_service.add_items()) ◄───────┘
```

- Items are created as `ACTIVE` via `item_service.add_items()`
- Items flagged as possible duplicates are created as `PENDING` via `item_service.hold_pending()`; a `PendingConfirmation` row is created simultaneously
- When a user confirms, Claude calls `add_items()` with the resolved item, creating a new ACTIVE item (the PENDING item and its `PendingConfirmation` remain in the DB as a record)

---

## Notable Constraints

| Constraint | Column | Purpose |
|-----------|--------|---------|
| UNIQUE | `users.phone_number` | One user record per phone number |
| UNIQUE (nullable) | `messages.twilio_sid` | Inbound deduplication; NULL for all outbound |
| UNIQUE | `brand_preferences.item_name` | One brand per item name; upsert pattern |
```

- [ ] **Step 2: Verify against spec**

Check that `docs/database.md` covers every item listed in the spec:
- [ ] All 6 tables with columns, types, constraints, and FKs
- [ ] FK relationship diagram
- [ ] ShoppingList state machine with service call labels
- [ ] Item state machine with PendingConfirmation linkage
- [ ] All 3 notable constraints table
- [ ] Seeded data note (startup, not migration, idempotent)
- [ ] PendingConfirmation expiry is informational only

- [ ] **Step 3: Commit**

```bash
git add docs/database.md
git commit -m "docs: add database schema, relationships, and state machine documentation"
```

---

## Task 5: `docs/tools.md`

**Files:**
- Create: `docs/tools.md`

- [ ] **Step 1: Write the file**

Create `docs/tools.md` with this exact content:

```markdown
# Claude Tool-Use Loop

## Loop Mechanics

The tool-use loop runs inside `orchestrator.handle_message()` in `app/agent/orchestrator.py`.

**Setup:**
1. `context_builder.build_system_prompt(user, db)` queries the DB and returns the full system prompt string: current active list items grouped by category, all brand preferences, pending confirmations for this user, and the last 10 messages in chronological order
2. Model is selected (see Model Selection below)
3. Messages list is initialized: `[{"role": "user", "content": body}]`

**Loop (max 10 iterations):**

```python
while iteration < 10:
    response = anthropic.messages.create(
        model=model,
        system=system_prompt,
        tools=TOOLS,          # from tool_definitions.py
        messages=messages,
        max_tokens=1024,
    )

    if response.stop_reason == "end_turn":
        # Extract text content, send via SMS, break

    elif response.stop_reason == "tool_use":
        # For each tool_use block in response.content:
        #   result = tool_executor.execute(tool_name, tool_input, user_id, db)
        #   Append assistant message + tool_result to messages
        # Continue loop

    else:
        # Send fallback SMS, break

    iteration += 1
```

**Loop exhaustion:** If 10 iterations complete without `end_turn`, a fallback SMS is sent to the user.

**Exception handling:** The entire loop is wrapped in a top-level try/except. Any unhandled exception sends a fallback SMS.

---

## Model Selection

```python
use_sonnet = (
    bool(pending_confirmations)          # context has unresolved pending items
    or (len(items) > 1 and any_brands)   # multi-item message with brand preferences
)
model = settings.sonnet_model if use_sonnet else settings.haiku_model
```

- **Haiku** (`claude-haiku-4-5-20251001`): default; handles simple add/check/send
- **Sonnet** (`claude-sonnet-4-6`): used when more reasoning is needed — resolving pending confirmations or handling brand context across multiple items simultaneously

---

## Tool Dispatch

`tool_executor.execute(tool_name, tool_input, user_id, db)` maps `tool_name` to a `_handle_<name>()` function.

Every handler:
- Calls the appropriate service function(s)
- Returns a plain JSON-serializable dict
- Catches all exceptions and returns `{"error": str(e)}` instead of raising

A tool failure never crashes the conversation loop — Claude sees the error dict and can recover.

---

## Tools

### `parse_items`

**Purpose:** Signal to Claude that it should parse the user's natural language input into structured item data before proceeding. Claude performs the actual parsing; this tool is an acknowledgment step that structures the workflow.

**Input:**
```json
{"text": "add milk and eggs"}
```

**Service call:** None

**Returns:**
```json
{"status": "ok"}
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

**Purpose:** Create a PENDING item (possible duplicate) and link it to the existing item via a `PendingConfirmation` record. Used when `check_duplicates` returns a possible match and the user needs to confirm.

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
{"item_name": "milk", "brand": "Organic Valley"}
```

**Returns (not found):**
```json
{"item_name": "milk", "brand": null}
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

**Purpose:** Transition the ACTIVE list to SENT and deliver the formatted list via SMS to the specified shopper.

**Input:**
```json
{"shopper_phone": "+15551234567"}
```

**Service calls:**
1. `list_service.send_list(db)` — transitions `ACTIVE → SENT`, sets `sent_at`
2. `list_service.get_list(db)` — retrieves formatted list data
3. `formatting.format_list(list_data)` — produces formatted text
4. `formatting.split_sms(text, max_chars=1500)` — splits into chunks if needed
5. `sms_service.send_sms(shopper_phone, chunk)` — called once per chunk

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
{"status": "archived", "list_id": 1, "new_list_id": 2}
```

**Constraint:** Raises `ValueError` if called on an ACTIVE list (must be SENT first). This is not enforced at the DB level — Claude is instructed via the system prompt to call `send_list` before `archive_list`. If Claude calls `archive_list` on an ACTIVE list, the exception is caught by `tool_executor` and returned as `{"error": "..."}`.

---

### `override_category`

**Purpose:** Manually reassign an item to a different category.

**Input:**
```json
{"item_id": 3, "category": "dairy"}
```

**Service call:** `item_service.override_category(item_id, category, db)`

The category string is normalized via `utils.category.normalize_category()` before saving. Valid canonical categories: PRODUCE, DAIRY, MEAT, SEAFOOD, DELI, BAKERY, FROZEN, CANNED_GOODS, DRY_GOODS, BEVERAGES, SNACKS, HOUSEHOLD, OTHER.

**Returns:**
```json
{"status": "updated", "item_id": 3, "category": "DAIRY"}
```

---

### `set_list_status`

**Purpose:** A convenience tool to send or archive the list using a string action, combining the effects of `send_list` or `archive_list`.

**Input (send):**
```json
{"action": "send", "shopper_phone": "+15551234567"}
```

**Input (archive):**
```json
{"action": "archive", "shopper_phone": null}
```

**Service calls:** Same as `send_list` or `archive_list` depending on `action`.

**Returns:** Same as the corresponding tool.

**Note:** `shopper_phone` is required when `action="send"`.

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

**4. Add or update service logic** in `app/services/` if the tool requires new DB operations.

---

## Known Constraints

- `archive_list` requires `SENT` status — not DB-enforced; Claude-instructed. Tool error if violated.
- Tool call order matters in the duplicate flow: `check_duplicates` must precede `add_items` or `hold_pending`. The system prompt instructs Claude on this ordering; there is no runtime enforcement.
- `send_list` sends SMS as a side effect inside a tool call. If the Claude loop fails after the tool succeeds, the SMS has already been delivered.
```

- [ ] **Step 2: Verify against spec**

Check that `docs/tools.md` covers every item in the spec:
- [ ] Loop mechanics: system prompt assembly, model selection, while loop (max 10 iterations), stop reason handling, fallback SMS
- [ ] Model selection: exact conditions for Haiku vs Sonnet
- [ ] Tool dispatch: error-as-dict pattern
- [ ] All 11 tools: parse_items, check_duplicates, add_items, hold_pending, lookup_brand_preference, save_brand_preference, get_list, send_list, archive_list, override_category, set_list_status
- [ ] For each tool: purpose, inputs, service calls, return value, non-obvious behavior
- [ ] 4-step extension guide with actual code
- [ ] Known constraints

- [ ] **Step 3: Commit**

```bash
git add docs/tools.md
git commit -m "docs: add Claude tool-use loop documentation with all 11 tools and extension guide"
```

---

## Task 6: `docs/testing.md`

**Files:**
- Create: `docs/testing.md`

- [ ] **Step 1: Write the file**

Create `docs/testing.md` with this exact content:

```markdown
# Testing

## Stack

- **pytest** — test runner
- **httpx** / **FastAPI TestClient** — HTTP-level testing
- **pytest-asyncio** — async test support
- **SQLite in-memory** — isolated DB per test, no file I/O, no dependency on production DB path

All tests live in `app/tests/`. Run the full suite with:

```bash
pytest app/tests/ -v
```

Run a single file:

```bash
pytest app/tests/test_orchestrator.py -v
```

---

## Fixtures (`app/tests/conftest.py`)

All fixtures are **function-scoped** — a fresh, isolated state for every test.

### `db`

Creates an in-memory SQLite engine using `StaticPool` (required for SQLite in-memory with multiple connections), runs `Base.metadata.create_all()` to build all tables, and seeds Chris and Donna as `User` records using `settings.chris_phone` and `settings.donna_phone`. Yields the session. On teardown: closes the session, drops all tables, disposes the engine.

```python
@pytest.fixture(scope="function")
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()

    for name, phone in [("Chris", settings.chris_phone), ("Donna", settings.donna_phone)]:
        if not session.query(User).filter(User.phone_number == phone).first():
            session.add(User(name=name, phone_number=phone))
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
```

### `client`

Depends on `db`. Builds a minimal FastAPI test app (no lifespan hook, no startup seed) that includes only the health router. Overrides the `get_db` FastAPI dependency to inject the `db` fixture session. Yields a `TestClient`.

```python
@pytest.fixture(scope="function")
def client(db: Session) -> TestClient:
    test_app = FastAPI(title="Shopping Agent (Test)")
    test_app.include_router(health_router)

    def override_get_db():
        yield db

    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app, raise_server_exceptions=True) as c:
        yield c
```

**Note:** `client` only includes the health router. Tests for `/webhook/sms` or `/tasks/timeout-check` construct their own test apps or call service and agent functions directly.

### `mock_anthropic`

Patches `app.agent.orchestrator.anthropic.Anthropic` to return a `MockAnthropicClient`. The mock wraps a `MockAnthropicMessages` object with a pre-configured response queue. Call `set_responses(list)` before the test to define what Claude will return. Responses are consumed in order; the mock raises `RuntimeError` if the queue is exhausted.

```python
@pytest.fixture
def mock_anthropic():
    client = MockAnthropicClient()
    with patch("app.agent.orchestrator.anthropic.Anthropic", return_value=client):
        yield client

# Usage in a test:
def test_add_items(mock_anthropic, mock_twilio, db):
    mock_anthropic.set_responses([
        # First call: Claude calls parse_items
        make_tool_use_response("parse_items", {"text": "add milk"}),
        # Second call: Claude calls check_duplicates
        make_tool_use_response("check_duplicates", {"items": [{"name": "milk"}]}),
        # Third call: Claude calls add_items
        make_tool_use_response("add_items", {"items": [{"name": "milk", "quantity": 1}]}),
        # Fourth call: Claude ends turn
        make_end_turn_response("Added milk to your list."),
    ])
    orchestrator.handle_message(user_id=1, body="add milk", db=db)
    assert mock_twilio.sent_messages[0]["body"] == "Added milk to your list."
```

### `mock_twilio`

Patches `app.agent.orchestrator.sms_service` with side effects from a `MockTwilioTracker`. Records all `send_sms(to, body)` and `send_error_sms(to)` calls to `tracker.sent_messages` as dicts `{"to": str, "body": str}`. Returns fake SID `"SM_fake_sid"` from `send_sms`.

```python
@pytest.fixture
def mock_twilio():
    tracker = MockTwilioTracker()
    with patch("app.agent.orchestrator.sms_service") as mock_svc:
        mock_svc.send_sms.side_effect = tracker.send_sms
        mock_svc.send_error_sms.side_effect = tracker.send_error_sms
        yield tracker

# Usage in a test:
def test_unknown_number(mock_twilio, db):
    # After calling something that sends an error SMS...
    assert len(mock_twilio.sent_messages) == 1
    assert mock_twilio.sent_messages[0]["body"] == "__error__"
```

---

## Test File Inventory

| File | What It Covers |
|------|---------------|
| `test_models.py` | ORM model construction, enum values, FK relationships, unique constraint enforcement |
| `test_health.py` | `GET /health` returns `{"status": "ok"}` with HTTP 200 |
| `test_webhook.py` | Inbound SMS: duplicate `MessageSid` returns 200 without reprocessing; unknown phone sends error SMS; valid request logs message and enqueues background task |
| `test_orchestrator.py` | Tool-use loop: model selection (Haiku vs Sonnet conditions), tool dispatch routing, `end_turn` text extraction and SMS send, loop exhaustion (10 iterations) → fallback SMS, Claude API exception → fallback SMS |
| `test_brand_service.py` | `get_brand_preference`: found (case-insensitive), not found; `save_brand_preference`: creates new record, updates existing record |
| `test_duplicate_service.py` | Score below threshold → clear; score at/above threshold → possible_duplicate; empty active list → all clear |
| `test_item_service.py` | `add_items`: creates Item records, auto-applies stored brand preference when brand not provided; `hold_pending`: creates PENDING Item and PendingConfirmation; `override_category`: updates item category |
| `test_list_service.py` | `get_list`: returns items grouped by category with PENDING annotation; `send_list`: transitions ACTIVE→SENT, sets sent_at; `archive_list`: transitions SENT→ARCHIVED, sets archived_at, creates new ACTIVE list |
| `test_sms_formatting.py` | `format_list`: header with date, categories in canonical order, items with quantity/unit/brand, footer; `split_sms`: single chunk (no prefix), multi-chunk (prefixed, footer on last), oversized single category (repeated header on continuation) |
| `test_timeout_check.py` | `run_timeout_check`: finds SENT lists older than threshold; skips if timeout prompt already sent (idempotency); sends SMS to all users; logs outbound Message records with twilio_sid=None |
```

- [ ] **Step 2: Verify against spec**

Check that `docs/testing.md` covers every item in the spec:
- [ ] Test stack (pytest, httpx, pytest-asyncio, in-memory SQLite)
- [ ] Test location and run command
- [ ] `db` fixture: scope, setup steps, seed data, teardown
- [ ] `client` fixture: scope, dependency, no lifespan, dependency override, health-router-only note
- [ ] `mock_anthropic` fixture: patch target, response queue, usage example
- [ ] `mock_twilio` fixture: patch target, sent_messages tracker, usage example
- [ ] All 10 test files in inventory table

- [ ] **Step 3: Commit**

```bash
git add docs/testing.md
git commit -m "docs: add testing infrastructure documentation with fixture details and test inventory"
```

---

## Self-Review Checklist

After completing all 6 tasks, verify:

- [ ] All 6 files exist: `CLAUDE.md`, `docs/architecture.md`, `docs/dataflow.md`, `docs/database.md`, `docs/tools.md`, `docs/testing.md`
- [ ] `CLAUDE.md` links to all 5 `docs/` files
- [ ] Tool count is consistent: 11 tools listed in both `CLAUDE.md` layer map description and `docs/tools.md`
- [ ] State machine transitions match between `docs/dataflow.md` (step descriptions) and `docs/database.md` (diagrams)
- [ ] Model names match throughout: `claude-haiku-4-5-20251001` and `claude-sonnet-4-6`
- [ ] Duplicate threshold value (85) is consistent in `docs/dataflow.md` and `docs/tools.md`
- [ ] Timeout value (8 hours) is consistent in `docs/dataflow.md` and `docs/database.md`
- [ ] `docs/testing.md` note about `client` only including health router matches `docs/architecture.md` router list
