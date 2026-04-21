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
Owns the Claude tool-use loop: assembles context, selects model, drives the loop, handles stop reasons, and sends the final SMS response. Does **not** own list or item business logic — that lives in services.

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
By default the loop uses `claude-haiku-4-5-20251001` (fast, cheap). It upgrades to `claude-sonnet-4-6` based on a string inspection of the already-assembled system prompt: if the prompt contains the word `"pending"` (indicating a pending confirmation exists) or contains both `"brand"` and more than two dashes (used as a proxy for a list with multiple items). The check is text-based — it does not make additional DB queries at decision time. See `docs/tools.md` for the exact logic.

### Tool Exception Isolation
Every handler in `tool_executor.py` wraps its logic in try/except and returns `{"error": "..."}` on failure rather than raising. This means a single tool failure does not crash the conversation — Claude sees the error and can recover or inform the user.

## Intentional Absences

These are **not** missing features — they are deliberate scope decisions for this household use case:

- **No authentication**: the system trusts that only known phone numbers will text it; access is controlled by Twilio number configuration
- **No multi-household support**: one global shopping list, two hardcoded users
- **No outbound SID tracking**: `sms_service.send_sms()` returns the Twilio SID but it is not persisted; outbound `Message` records have `twilio_sid=None`
- **No expired PendingConfirmation cleanup**: `expires_at` is informational; no background job removes stale rows
