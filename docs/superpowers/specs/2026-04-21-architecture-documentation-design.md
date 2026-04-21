# Architecture Documentation Design
_Date: 2026-04-21_

## Goal

Document the shopping-agent application's architecture and dataflow in anticipation of expanding the system's scope — specifically adding new capabilities (e.g., recipe integration, store-specific lists, ordering) and new delivery channels (e.g., web UI, voice interface).

## Audience

- Future solo developer returning after months away
- New developer onboarding to contribute
- AI agents (e.g., Claude Code) given context to work safely in the codebase

## Output Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI-agent context: concise orientation, layer map, extension points, pointers to `docs/` |
| `docs/architecture.md` | System overview, layer diagram, component responsibilities, key design decisions |
| `docs/dataflow.md` | All message paths end-to-end, step-by-step |
| `docs/database.md` | Schema tables, FK relationships, state machines, notable constraints |
| `docs/tools.md` | Claude tool-use loop mechanics, all 11 tools, extension guide |
| `docs/testing.md` | Test infrastructure, fixtures, mock strategy, test file inventory |

---

## `CLAUDE.md`

**Contents:**
- One-sentence app summary; two users (Chris + Donna); SMS-driven household shopping list
- Tech stack: FastAPI, SQLAlchemy/SQLite, Twilio, Anthropic Claude API, Railway
- Entry points: `/webhook/sms`, `/tasks/timeout-check`, `/health`
- Key architectural constraint: webhook must return immediately — Claude API calls happen in a FastAPI background task
- Layer map: routers → agent (orchestrator → context_builder → tool_executor) → services → models
- Extension points: adding a tool (tool_definitions.py + tool_executor.py); adding a channel (new router + orchestrator.handle_message())
- Pointers to `docs/` for full detail
- What NOT to do: don't call Claude synchronously in a request handler; don't add list state transitions outside list_service.py

---

## `docs/architecture.md`

**Contents:**
- Purpose, users, deployment context (Railway + SQLite volume)
- Text layer diagram: HTTP → Agent → Services → Models/DB → External
- Component responsibilities — one paragraph per major component; what it owns and what it does NOT own
- Key design decisions worth preserving:
  - Background task pattern (reason: Twilio timeout)
  - Idempotency via MessageSid (reason: Twilio retry behavior)
  - Model selection logic: Haiku vs Sonnet (reason: cost/capability tradeoff)
  - Tool exception isolation (reason: keep conversation alive through tool failures)
- What is intentionally absent from the codebase (no auth, no multi-household, no outbound SID tracking)

---

## `docs/dataflow.md`

**Contents (one numbered step-list per path):**

1. Happy path — add items: SMS in → webhook → idempotency check → user lookup → background task → context build → Claude loop → parse_items → check_duplicates → add_items → end_turn → SMS out
2. Duplicate detection path: check_duplicates returns match → hold_pending → user prompted → user replies → resolution on next turn
3. Send list path: send_list → ACTIVE→SENT → format + split → SMS chunk(s) to shopper
4. Archive path: DONE reply → archive_list → SENT→ARCHIVED → new ACTIVE list created
5. Timeout check path: Railway cron → POST /tasks/timeout-check → SENT lists older than 8h → idempotency check → timeout SMS to all users
6. Error paths: unknown phone, tool failure mid-loop, loop exhaustion (10 iterations), Claude API exception

---

## `docs/database.md`

**Contents:**
- All 6 tables: columns, types, constraints, FKs (one table per section)
- Text FK relationship diagram
- State machine: `ShoppingList.status` — ACTIVE → SENT → ARCHIVED with triggering service calls; archive creates new ACTIVE list
- State machine: `Item.status` — ACTIVE ↔ PENDING with PendingConfirmation linkage
- Notable constraints: messages.twilio_sid unique, brand_preferences.item_name unique, users.phone_number unique
- Seeded data: Chris and Donna seeded at startup (not via migration) — intentional
- Expired PendingConfirmation rows are not auto-cleaned; expires_at is informational only

---

## `docs/tools.md`

**Contents:**
- Loop mechanics: system prompt assembly, model selection, while loop (max 10 iterations), stop reason handling, fallback SMS
- Model selection: Haiku by default; Sonnet if pending confirmations exist OR (item count > 1 AND any item has a brand)
- Tool dispatch: how tool_executor.execute() routes calls; errors returned as dicts (not raised) to keep loop alive
- All 11 tools — for each: purpose, inputs, service calls, return value, non-obvious behavior:
  - parse_items, check_duplicates, add_items, hold_pending
  - lookup_brand_preference, save_brand_preference
  - get_list, send_list, archive_list
  - override_category, set_list_status
- Extension guide: 4 steps to add a new tool
- Known constraints: archive_list requires SENT status (not DB-enforced; Claude-instructed)

---

---

## `docs/testing.md`

**Contents:**
- Test stack: pytest, httpx, pytest-asyncio; in-memory SQLite (not the production DB path)
- Test location: `app/tests/` — 10 test files + `conftest.py`
- **`db` fixture**: function-scoped; creates a fresh in-memory SQLite engine, runs `Base.metadata.create_all`, seeds Chris and Donna from `settings`, yields the session, drops all tables and disposes engine on teardown
- **`client` fixture**: function-scoped; builds a minimal FastAPI test app (no lifespan) that includes only the health router; overrides `get_db` dependency with the `db` fixture session; yields a `TestClient`
- **`mock_anthropic` fixture**: patches `app.agent.orchestrator.anthropic.Anthropic`; returns a `MockAnthropicClient` with a pre-configured response queue (`set_responses(list)`); calls consume responses in order; raises `RuntimeError` if queue is exhausted
- **`mock_twilio` fixture**: patches `app.agent.orchestrator.sms_service`; returns a `MockTwilioTracker` that records all `send_sms` and `send_error_sms` calls to `tracker.sent_messages`; returns fake SID `"SM_fake_sid"`
- Test file inventory with what each covers:
  - `test_models.py` — ORM model construction and constraints
  - `test_health.py` — GET /health
  - `test_webhook.py` — POST /webhook/sms (idempotency, unknown number, happy path)
  - `test_orchestrator.py` — tool-use loop, model selection, fallback SMS
  - `test_brand_service.py` — get/save brand preference, case-insensitive lookup
  - `test_duplicate_service.py` — fuzzy match thresholds, clear vs possible_duplicate classification
  - `test_item_service.py` — add_items (brand auto-apply), hold_pending, override_category
  - `test_list_service.py` — get_list, send_list, archive_list, state transitions
  - `test_sms_formatting.py` — format_list, split_sms (single chunk, multi-chunk, oversized category)
  - `test_timeout_check.py` — run_timeout_check, idempotency, message logging

---

## Non-Goals

- Do not document deployment procedures
- Do not guess at anything unclear in the code — note it explicitly if ambiguous
