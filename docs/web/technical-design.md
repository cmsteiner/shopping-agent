# Technical Design

## Overview

This design extends the current FastAPI/SQLAlchemy SMS app into a shared mobile web interface without breaking the existing SMS/Codex flow. It fits the current architecture in `app/main.py`, `app/services/item_service.py`, `app/services/list_service.py`, and the documented layer boundaries in `docs/architecture.md`.

## Design Goals

- Keep the current backend as the source of truth for list and trip state.
- Add web APIs and real-time updates without introducing synchronous AI work into request handlers.
- Preserve the service-layer ownership rules already established in the repo.
- Support concurrent edits from two phones with explicit conflict resolution.
- Make the UI feel immediate on add/edit/check, even when backend enrichment or conflict validation follows.

## Architecture

Add a new web channel alongside SMS, not a replacement for it.

Backend additions:

- `app/routers/web.py`: serves the app shell or static assets if the frontend is bundled into FastAPI
- `app/routers/api.py`: JSON endpoints for list, items, categories, trip actions, conflict resolution, and duplicate resolution
- `app/routers/realtime.py`: SSE endpoint for live updates
- `app/services/category_service.py`: create/rename/delete categories and move validation
- `app/services/trip_service.py`: start trip, toggle purchased state, finish trip, carryover flow
- `app/services/realtime_service.py`: append/list event stream messages for SSE
- `app/services/conflict_service.py`: optimistic concurrency checks and conflict payload generation
- `app/schemas/`: Pydantic request/response models for web APIs
- `frontend/` or `app/static/`: mobile web UI

Recommended frontend:

- a small React/Vite SPA, built to static assets and served by FastAPI
- one route: `/app/<shared-token>` or similar private-link path
- client state managed with server-backed optimistic updates plus SSE event subscription

## Why SSE

Use Server-Sent Events, not polling or WebSockets.

Reasoning:

- the app is mostly server-to-client fanout of small state changes
- two mobile clients plus SMS updates is low-volume and one-way
- SSE is simpler to run on FastAPI and easier to reason about than WebSockets
- polling would work, but conflict handling and immediate SMS-sync would feel worse

Recommended pattern:

- client loads initial snapshot via `GET /api/app-state`
- client opens `GET /api/events/stream?token=...&last_event_id=...`
- server emits item/category/trip/list events in order
- on reconnect, client resumes from `Last-Event-ID`; if gap is too large, server tells client to refetch snapshot

## State Model Changes

The current schema does not yet represent active shopping trips, purchased status, category management as first-class data, or concurrency versions. v1 needs schema expansion.

Recommended new/changed tables:

### 1. `shopping_lists`

- keep existing states
- add `version INTEGER NOT NULL DEFAULT 1`

### 2. `items`

Add:

- `notes TEXT NULL`
- `is_purchased BOOLEAN NOT NULL DEFAULT 0`
- `purchased_at DATETIME NULL`
- `new_during_trip BOOLEAN NOT NULL DEFAULT 0`
- `sort_name VARCHAR` optional normalized name for stable alpha ordering
- `version INTEGER NOT NULL DEFAULT 1`
- `updated_at DATETIME NOT NULL`

### 3. `shopping_trips`

New table:

- `id`
- `list_id` FK unique for active/current trip relation
- `status` enum: `ACTIVE`, `COMPLETED`
- `started_at`
- `completed_at`
- `version INTEGER NOT NULL DEFAULT 1`

### 4. `categories`

New table:

- `id`
- `name`
- `normalized_name`
- `sort_order INTEGER NOT NULL`
- `version INTEGER NOT NULL DEFAULT 1`
- `created_at`
- `updated_at`

### 5. `list_events`

New append-only event table for SSE replay:

- `id` bigint/autoincrement
- `event_type`
- `list_id`
- `entity_type`
- `entity_id`
- `payload_json`
- `created_at`

### 6. `pending_web_conflicts`

Optional if conflict resolution needs a durable server-side choice record:

- `id`
- `entity_type`
- `entity_id`
- `client_version`
- `server_version`
- `client_payload_json`
- `server_payload_json`
- `status`

### 7. `pending_trip_carryovers`

Optional if finish flow is multi-step:

- `id`
- `trip_id`
- `item_id`
- `decision` nullable until chosen

## Compatibility Note

The current `items.category` string field can be kept short-term for compatibility, but the cleaner design is:

- add `category_id` FK
- keep `category` temporarily as denormalized text during migration
- gradually move reads/writes to `category_id`

Recommendation:

- add `category_id` now
- leave `category` as a temporary backward-compatible field during migration

## Domain Rules

- exactly one current active list
- zero or one active trip for the current list
- trip can start only if at least one non-pending item exists
- items added during an active trip get `new_during_trip=true`
- checking an item clears `new_during_trip`
- finishing a trip archives the current list and creates a new active list
- unpurchased items are reviewed item-by-item before carryover completes
- duplicate detection still uses the existing pending-confirmation flow, but the web UI presents it as a modal instead of SMS text

## API Design

Core snapshot:

- `GET /api/app-state?token=...`

Returns:

- current list metadata
- active trip metadata or null
- ordered categories
- items grouped by category
- any pending duplicate/conflict prompts relevant to the current client session

Items:

- `POST /api/items`
- `PATCH /api/items/{id}`
- `DELETE /api/items/{id}`
- `POST /api/items/{id}/toggle-purchased`

Categories:

- `POST /api/categories`
- `PATCH /api/categories/{id}`
- `DELETE /api/categories/{id}`

Trip:

- `POST /api/trips/start`
- `POST /api/trips/{id}/finish/prepare`
- `POST /api/trips/{id}/finish/complete`

Conflicts:

- `POST /api/conflicts/resolve`

Duplicates:

- `POST /api/duplicates/{pending_confirmation_id}/resolve`

Realtime:

- `GET /api/events/stream?token=...`

## Optimistic Concurrency

Use version-based optimistic concurrency on mutable entities.

Client sends:

- `base_version` with every item/category/trip mutation

Server behavior:

- if `base_version` matches current row version, apply mutation, increment version, emit event
- if not, return `409 Conflict` with:
  - entity id/type
  - client attempted values
  - current server values
  - current version
  - merge options if applicable

This fits the `finish typing first, then show both versions` requirement:

- client buffers the user’s inline edit locally
- save request uses the version from when editing started
- if stale, client receives both payloads and opens the chooser

## Conflict UX Contract

For item/category edit conflicts, the API should return:

```json
{
  "type": "conflict",
  "entity_type": "item",
  "entity_id": 42,
  "field_conflicts": {
    "name": {"client": "green onions", "server": "scallions"},
    "quantity": {"client": "2", "server": "1"}
  },
  "client_payload": {...},
  "server_payload": {...},
  "server_version": 8
}
```

Resolution API:

- choose server version
- choose client version and overwrite
- optionally choose per-field merge later, but not required for v1

Recommendation for v1:

- whole-record choice only

## Duplicate Validation Contract

The backend already has duplicate detection and pending confirmation concepts. Reuse them.

Suggested flow:

1. `POST /api/items` creates optimistic item response immediately with temp values.
2. Backend runs duplicate check before finalizing.
3. If clear:
   - create ACTIVE item
   - emit `item.created`
4. If duplicate:
   - create `PENDING` item + `PendingConfirmation`
   - emit `item.pending_duplicate`
5. UI shows modal with existing and new item:
   - `merge`
   - `keep separate`
   - `cancel`

Resolution:

- `merge`: update existing item quantity or merge notes according to backend rule, remove pending item
- `keep separate`: convert pending item to active item
- `cancel`: delete pending item

## Event Model

Emit a normalized event whenever web or SMS changes shared state.

Suggested event types:

- `list.snapshot_required`
- `item.created`
- `item.updated`
- `item.deleted`
- `item.pending_duplicate`
- `item.duplicate_resolved`
- `category.created`
- `category.renamed`
- `category.deleted`
- `trip.started`
- `trip.updated`
- `trip.completed`
- `trip.finish_review_required`
- `conflict.detected`

Each event should include:

- `event_id`
- `event_type`
- `list_id`
- `occurred_at`
- `payload`

The SSE stream should be driven from the same service-layer mutations that currently update the DB, so SMS and web changes both flow through the same event writer.

## Frontend State Design

Use a normalized client store with:

- `list`
- `trip`
- `categories`
- `itemsById`
- `categoryOrder`
- `pendingMutations`
- `activeConflict`
- `activeDuplicatePrompt`
- `connectionStatus`

Behavior:

- initial load from snapshot
- mutations update local state optimistically
- server responses reconcile temp ids/placeholders
- SSE events patch shared state
- if an SSE event arrives for an entity under local edit, don’t interrupt typing; mark it stale and surface conflict after save attempt or blur

## UI Structure

Single screen with sheet/modal overlays.

Main list screen:

- top banner: trip status with start time
- add-item form
- grouped category sections
- inline editable item rows
- category controls inline or per-section header
- start trip / finish trip action area

Modals:

- duplicate validation modal
- conflict resolution modal
- finish-trip carryover modal
- delete-category confirmation modal

Error states:

- inline retry chip or banner on failed autosave
- connection lost banner if SSE disconnects

## Recommended Screen Behavior

- Add-item form pinned near top for fast entry.
- Category headers show rename/delete affordances.
- Inline row supports tap-to-edit name, qty, category, notes.
- Checkbox toggles purchased/unpurchased instantly.
- `New` badge shown in row until item is checked.
- No success toast spam.

## Serving the Private Link

Since v1 has no auth, use a shared secret path token.

Recommendation:

- configure `WEB_SHARED_TOKEN` in env
- app served at `/app/{token}`
- API and SSE require same token, either in path or header
- reject requests with wrong/missing token

This is not strong security, but it matches the agreed v1 model and is more explicit than a plain unlisted root URL.

## Backend Integration Strategy

Respect current layer boundaries.

Routers:

- validate token
- parse request
- open DB session
- call services
- return JSON/SSE

Services:

- own all mutations
- increment versions
- write `list_events`
- never let routers mutate DB directly

Agent/SMS integration:

- existing SMS flows continue using current services
- service methods gain event emission so SMS-originated changes appear live in web
- no Codex calls are introduced into web request handlers

## Migration Plan

1. Add new tables and columns via Alembic:
   - `shopping_trips`
   - `categories`
   - `list_events`
   - item fields for notes/purchased/new/version/updated_at
2. Seed categories from current canonical category list.
3. Backfill item category references.
4. Add web API schemas and routers.
5. Refactor item/list mutations to emit events.
6. Build frontend snapshot + SSE sync.
7. Add conflict and duplicate resolution flows.
8. Add trip finish carryover flow.

## Testing Plan

Backend tests:

- API snapshot response
- item create/edit/delete
- autosave conflict `409`
- duplicate modal flow
- category rename/delete rules
- trip start restrictions
- trip finish carryover decisions
- SSE event emission on web mutations
- SSE event emission on SMS/service mutations

Frontend tests:

- empty list state
- optimistic add with placeholders
- inline autosave
- stale edit conflict modal
- duplicate validation modal
- `New` badge lifecycle
- finish trip item-by-item carryover flow
- SSE-driven live updates

End-to-end tests:

- web client A edits item, client B updates live
- SMS adds item, open web client updates live
- concurrent category rename conflict
- finish trip with mixed purchased/unpurchased items

## Open Implementation Choices

Several choices still need engineering decisions:

- React/Vite SPA served by FastAPI vs server-rendered HTMX-style UI
- `category_id` migration now vs later
- how merge should work for duplicate items
- how far to push optimistic UI for delete and finish-trip flows

Recommendation:

- React/Vite SPA
- SSE
- version-based optimistic concurrency
- `category_id` now
- append-only `list_events` table for replay/reconnect

## Suggested File/Module Layout

- `app/routers/web.py`
- `app/routers/api.py`
- `app/routers/realtime.py`
- `app/services/category_service.py`
- `app/services/trip_service.py`
- `app/services/conflict_service.py`
- `app/services/realtime_service.py`
- `app/schemas/web.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/events.ts`
- `frontend/src/store.ts`
- `frontend/src/components/ListScreen.tsx`
- `frontend/src/components/ItemRow.tsx`
- `frontend/src/components/CategorySection.tsx`
- `frontend/src/components/ConflictModal.tsx`
- `frontend/src/components/DuplicateModal.tsx`
- `frontend/src/components/FinishTripModal.tsx`
