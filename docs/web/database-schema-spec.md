# Database / Schema Spec

## Goals

- Add web-app state without breaking the existing SMS/Codex flow.
- Preserve current service boundaries.
- Support real-time sync, trip state, optimistic concurrency, and duplicate/conflict workflows.
- Keep migration risk manageable.

## Schema Changes

### 1. `shopping_lists`

Existing table stays, with one additive column:

- `version INTEGER NOT NULL DEFAULT 1`

Purpose:

- supports list-level concurrency if needed
- useful when trip completion replaces the active list

No change to existing statuses:

- `ACTIVE`
- `SENT`
- `ARCHIVED`

### 2. `items`

Add these columns:

- `notes TEXT NULL`
- `category_id INTEGER NULL FK -> categories.id`
- `is_purchased BOOLEAN NOT NULL DEFAULT 0`
- `purchased_at DATETIME NULL`
- `new_during_trip BOOLEAN NOT NULL DEFAULT 0`
- `updated_at DATETIME NOT NULL`
- `version INTEGER NOT NULL DEFAULT 1`

Keep existing columns:

- `id`
- `list_id`
- `name`
- `quantity`
- `unit`
- `brand_pref`
- `category` temporary compatibility field
- `status`
- `added_by`
- `created_at`

Recommendation:

- keep `category` during transition
- add `category_id`
- keep both in sync in the service layer for v1
- once web and SMS fully use `category_id`, remove `category` later

### 3. `categories`

New table:

- `id INTEGER PK`
- `name VARCHAR(100) NOT NULL`
- `normalized_name VARCHAR(100) NOT NULL UNIQUE`
- `sort_order INTEGER NOT NULL`
- `created_at DATETIME NOT NULL`
- `updated_at DATETIME NOT NULL`
- `version INTEGER NOT NULL DEFAULT 1`

Purpose:

- first-class category management
- backend-defined ordering
- rename/delete support
- stable IDs for API and conflict handling

### 4. `shopping_trips`

New table:

- `id INTEGER PK`
- `list_id INTEGER NOT NULL FK -> shopping_lists.id`
- `status VARCHAR NOT NULL`
- `started_at DATETIME NOT NULL`
- `completed_at DATETIME NULL`
- `version INTEGER NOT NULL DEFAULT 1`

Statuses:

- `ACTIVE`
- `COMPLETED`

Constraints:

- at most one `ACTIVE` trip at a time
- app-enforced is fine for SQLite v1
- add a partial unique index later if needed and supported

### 5. `list_events`

New append-only event table:

- `id INTEGER PK`
- `list_id INTEGER NULL FK -> shopping_lists.id`
- `event_type VARCHAR(100) NOT NULL`
- `entity_type VARCHAR(50) NOT NULL`
- `entity_id INTEGER NULL`
- `payload_json TEXT NOT NULL`
- `created_at DATETIME NOT NULL`

Purpose:

- SSE replay
- unified live updates for web and SMS-originated changes
- debugging/event audit for state changes

### 6. Reuse `pending_confirmations`

Keep the current table and model.

It already fits duplicate resolution well:

- `item_id`
- `existing_item_id`
- `triggered_by`
- `expires_at`

For web v1, it becomes the durable backing store for duplicate modals.

## Model Updates

### `Item`

Add fields:

- `notes`
- `category_id`
- `is_purchased`
- `purchased_at`
- `new_during_trip`
- `updated_at`
- `version`

Relationships:

- `category = relationship("Category", back_populates="items")`

Behavior:

- increment `version` on every mutation
- update `updated_at` on every mutation

### `Category`

New ORM model with:

- `items = relationship("Item", back_populates="category")`

### `ShoppingTrip`

New ORM model with:

- relationship to `ShoppingList`

### `ShoppingList`

Add:

- `version`
- optional relationship `trips`

## Migration Plan

### Migration 1: categories + item web fields

Create `categories`.
Add new item columns:

- `notes`
- `category_id`
- `is_purchased`
- `purchased_at`
- `new_during_trip`
- `updated_at`
- `version`

Backfill:

- create categories from current canonical category set plus any distinct item category strings already in data
- map existing `items.category` strings to `categories.id`
- set `updated_at = created_at` for existing rows
- set `version = 1`

### Migration 2: shopping trips

Create `shopping_trips`.

No backfill needed unless historical trips are inferred from `SENT` lists, which is not recommended for v1.

### Migration 3: event log

Create `list_events`.

No backfill required.

## Indexes

Recommended indexes:

### `items`

- index on `list_id`
- index on `category_id`
- index on `(list_id, status)`
- index on `(list_id, is_purchased)`
- index on `updated_at`

### `categories`

- unique index on `normalized_name`
- index on `sort_order`

### `shopping_trips`

- index on `list_id`
- index on `status`

### `list_events`

- index on `id`
- index on `(list_id, id)`
- index on `created_at`

## Service Layer Changes

### `item_service.py`

Expand responsibilities:

- create item with placeholder/default category and quantity behavior
- update item fields inline
- delete item
- toggle purchased
- clear `new_during_trip` when item is checked
- increment item version and `updated_at`
- emit `list_events`

Likely functions:

- `update_item(...)`
- `delete_item(...)`
- `toggle_purchased(...)`

### `list_service.py`

Keep ownership of list lifecycle transitions.
Extend:

- version bump on archive/new list creation
- event emission on list replacement

### `category_service.py`

Owns:

- create category
- rename category
- delete category
- validation that delete is blocked when items remain
- sync of `items.category` compatibility text during v1

### `trip_service.py`

Owns:

- start trip
- get active trip
- prepare finish flow
- complete finish flow
- carry over selected unchecked items into new active list

This keeps trip logic out of routers and out of `list_service.py`, while still allowing `trip_service` to call `list_service.archive_list()` or equivalent list lifecycle helpers.

### `realtime_service.py`

Owns:

- writing `list_events`
- reading events after `Last-Event-ID`
- serializing SSE payloads

### `conflict_service.py`

Owns:

- version mismatch detection helpers
- building conflict payloads for item/category responses
- whole-record overwrite resolution

## Compatibility Rules

To avoid breaking SMS flows immediately:

- SMS/Codex code may keep passing category strings for now.
- Service layer resolves category strings to `category_id`.
- Service layer also writes the denormalized `items.category` text during v1.
- Existing `list_service.get_list()` can keep returning grouped categories while gradually shifting to `category_id`-backed ordering.

## Suggested SQLAlchemy Enum Additions

Add new enums:

`TripStatus`

- `ACTIVE`
- `COMPLETED`

No need to change current `ItemStatus` or `ListStatus` for v1.

## Data Integrity Rules

Enforce in service layer:

- only one active list
- only one active trip
- trip start requires at least one non-pending item
- purchased toggle only allowed during active trip
- category delete blocked if any items still reference it
- category rename updates denormalized `items.category`
- finish trip archives current list and creates new active list
- carryover items are recreated on new active list as unpurchased

## Event Emission Rules

Emit an event from the same transaction boundary as each successful mutation.

Examples:

- item create -> `item.created`
- item edit -> `item.updated`
- item delete -> `item.deleted`
- duplicate pending -> `item.pending_duplicate`
- category rename -> `category.updated`
- trip start -> `trip.started`
- trip finish -> `trip.completed`
- new active list -> `list.replaced`

## Recommended Alembic Order

1. Add `categories` and extend `items`
2. Backfill category rows and `category_id`
3. Add `shopping_trips`
4. Add `list_events`
5. Update ORM models
6. Refactor services to use new columns
7. Add web routers on top of service layer

## Implementation Notes

- SQLite is fine for this v1 schema.
- Use integer `version` columns instead of timestamps for concurrency.
- Use `updated_at` for UI freshness and debugging, not concurrency.
- Keep `pending_confirmations` as-is; it already gives a strong duplicate workflow.
