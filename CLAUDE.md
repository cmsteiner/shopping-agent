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
app/
  routers/       ← HTTP handling, signature validation, idempotency
  agent/         ← Claude tool-use loop
    orchestrator.py       (loop driver)
    context_builder.py    (system prompt assembly)
    tool_definitions.py   (Anthropic tool schemas)
    tool_executor.py      (tool dispatch → services)
  services/      ← Business logic, DB mutations
  models/        ← SQLAlchemy ORM models
  tasks/         ← Background task logic (timeout check)
  utils/         ← SMS formatting, category normalization

Call flow: routers → agent → services → models
```

## Extension Points

**Adding a new tool:**
1. Add schema to `app/agent/tool_definitions.py`
2. Add handler `_handle_<name>()` to `app/agent/tool_executor.py`
3. Add service logic to `app/services/` if needed
4. If Claude needs explicit instructions about when to call the new tool, add a note to the system prompt in `app/agent/context_builder.py`

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
