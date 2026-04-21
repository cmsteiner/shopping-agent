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
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

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

# Usage in a test (simplified — real flows typically have more tool calls):
def test_add_items(mock_anthropic, mock_twilio, db):
    mock_anthropic.set_responses([
        # Each list entry is consumed by one loop iteration
        make_tool_use_response("parse_items", {"text": "add milk"}),
        # ... intermediate tool calls (check_duplicates, add_items) ...
        make_end_turn_response("Added milk to your list."),
    ])
    orchestrator.handle_message(user_id=1, body="add milk", db=db)
    assert mock_twilio.sent_messages[0]["body"] == "Added milk to your list."
```

### `mock_twilio`

Patches `app.agent.orchestrator.sms_service` with side effects from a `MockTwilioTracker`. Records all `send_sms(to, body)` and `send_error_sms(to)` calls to `tracker.sent_messages` as dicts `{"to": str, "body": str}`. Returns fake SID `"SM_fake_sid"` from `send_sms`. `send_error_sms` appends `{"to": str, "body": "__error__"}`.

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
| `test_webhook.py` | Inbound SMS: valid signature enqueues background task and logs message; invalid Twilio signature returns 403; duplicate `MessageSid` returns 200 without reprocessing; unknown phone sends error SMS and returns 200; development mode skips signature validation; tool executor exception sends fallback SMS without crashing |
| `test_orchestrator.py` | Tool-use loop: end_turn text extraction and SMS send, loop exhaustion → fallback SMS, Claude API exception → fallback SMS; Phase 3 flows: DONE command calls archive_list, CANCEL keeps list ACTIVE, duplicate detection creates PENDING item, preview retrieves list without changing status |
| `test_brand_service.py` | `get_brand_preference`: found (case-insensitive), not found; `save_brand_preference`: creates new record, updates existing record |
| `test_duplicate_service.py` | Score below threshold → clear; score at/above threshold → possible_duplicate; empty active list → all clear |
| `test_item_service.py` | `hold_pending`: creates PENDING Item and PendingConfirmation row, verifies expiry set to ~24h; `override_category`: updates item category, raises `ValueError` for missing item ID |
| `test_list_service.py` | `get_list`: returns items grouped by category with PENDING annotation; `send_list`: transitions ACTIVE→SENT, sets sent_at; `archive_list`: transitions SENT→ARCHIVED, sets archived_at, creates new ACTIVE list |
| `test_sms_formatting.py` | `format_list`: header with date, categories in canonical order, items with quantity/unit/brand, footer; `split_sms`: single chunk (no prefix), multi-chunk (prefixed, footer on last), oversized single category; `normalize_category`: canonical match, case-insensitive, unknown falls back to OTHER; `add_items` brand auto-apply: applies stored preference, does not override explicit brand |
| `test_timeout_check.py` | `run_timeout_check`: finds SENT lists older than threshold; skips if timeout prompt already sent (idempotency); sends SMS to all users; logs outbound Message records with twilio_sid=None |
