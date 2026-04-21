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
- Calling `archive_list()` when no SENT list exists raises `ValueError` (not DB-enforced; caught by `tool_executor`)

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
