# Build Checklist

Status legend:
- `[x]` Completed
- `[~]` Partially completed
- `[ ]` Not started

## Milestone A: Schema + Models

Goal: establish the database foundation.

- `[x]` Ticket A1: Add `categories` table via Alembic
  - Create columns: `id`, `name`, `normalized_name`, `sort_order`, `created_at`, `updated_at`, `version`
  - Add unique constraint on `normalized_name`

- `[x]` Ticket A2: Extend `items` table for web state
  - Add `notes`
  - Add `category_id`
  - Add `is_purchased`
  - Add `purchased_at`
  - Add `new_during_trip`
  - Add `updated_at`
  - Add `version`

- `[x]` Ticket A3: Add `shopping_trips` table via Alembic
  - Create columns: `id`, `list_id`, `status`, `started_at`, `completed_at`, `version`

- `[x]` Ticket A4: Add `list_events` table via Alembic
  - Create columns: `id`, `list_id`, `event_type`, `entity_type`, `entity_id`, `payload_json`, `created_at`

- `[x]` Ticket A5: Backfill categories and item category references
  - Seed canonical categories
  - Insert any existing distinct item category strings not already present
  - Populate `items.category_id`
  - Set `items.updated_at = items.created_at`
  - Set `version = 1` on backfilled rows

- `[x]` Ticket A6: Update SQLAlchemy models
  - Add new ORM models for `Category`, `ShoppingTrip`, `ListEvent`
  - Extend `Item` and `ShoppingList`
  - Wire relationships in `app/models/__init__.py`

- `[x]` Ticket A7: Add migration test coverage
  - Verify upgrade on empty DB
  - Verify upgrade on populated DB
  - Verify app startup after migration

## Milestone B: Core Services

Goal: make the backend capable of the new domain behavior.

- `[x]` Ticket B1: Add category lookup/create helpers
  - Resolve category names to IDs
  - Normalize names consistently
  - Preserve backend ordering

- `[~]` Ticket B2: Refactor `item_service.add_items()`
  - `notes` and `category_id` support are in place
  - `category` text synchronization is in place for update paths
  - Active-trip `new_during_trip` behavior is not implemented yet
  - Create-time event emission is not implemented yet

- `[x]` Ticket B3: Add `item_service.update_item()`
  - Support inline updates for `name`, `quantity`, `unit`, `notes`, `category_id`
  - Enforce optimistic concurrency with `base_version` at the API layer

- `[x]` Ticket B4: Add `item_service.delete_item()`
  - Delete immediately
  - Optional `base_version` enforcement remains loose in the route layer

- `[x]` Ticket B5: Add `item_service.toggle_purchased()`
  - Allow only during active trip
  - Set `is_purchased`
  - Set and clear `purchased_at`
  - Clear `new_during_trip` when checked

- `[x]` Ticket B6: Create `category_service.py`
  - `create_category`
  - `rename_category`
  - `delete_category`
  - Delete blocked when category still has items

- `[x]` Ticket B7: Create `trip_service.py`
  - `start_trip`
  - `get_active_trip`
  - `prepare_finish_trip`
  - `complete_finish_trip`

- `[x]` Ticket B8: Create `conflict_service.py`
  - Compare `base_version`
  - Build standardized `409` payloads
  - Support whole-record overwrite resolution

- `[x]` Ticket B9: Create `realtime_service.py`
  - Append `list_events`
  - Query events after event ID
  - Serialize event payloads for SSE

- `[~]` Ticket B10: Update `list_service.py` for trip completion
  - Trip completion behavior exists, but it currently lives in `trip_service.py`
  - `list_service.py` itself was not refactored to own this flow

## Milestone C: API Schemas + Routing

Goal: expose the agreed contract cleanly.

- `[x]` Ticket C1: Add shared-token config
  - Add `WEB_SHARED_TOKEN` to config
  - Document env var in `.env.example`

- `[x]` Ticket C2: Add token validation dependency
  - Read `X-App-Token`
  - Return `403` on invalid or missing token

- `[ ]` Ticket C3: Create `app/schemas/web.py`
  - Request models
  - Response models
  - Error models
  - Conflict models

- `[x]` Ticket C4: Add `GET /api/app-state`
  - Return full snapshot
  - Include list, trip, categories, grouped items, pending prompts

- `[x]` Ticket C5: Add item endpoints
  - `POST /api/items`
  - `PATCH /api/items/{id}`
  - `DELETE /api/items/{id}`
  - `POST /api/items/{id}/toggle-purchased`

- `[x]` Ticket C6: Add category endpoints
  - `POST /api/categories`
  - `PATCH /api/categories/{id}`
  - `DELETE /api/categories/{id}`

- `[x]` Ticket C7: Add trip endpoints
  - `POST /api/trips/start`
  - `POST /api/trips/{id}/finish/prepare`
  - `POST /api/trips/{id}/finish/complete`

- `[x]` Ticket C8: Add duplicate and conflict resolution endpoints
  - `POST /api/duplicates/{pending_confirmation_id}/resolve`
  - `POST /api/conflicts/resolve`

- `[~]` Ticket C9: Standardize error handling
  - `403`, `404`, `409`, `422` are in use
  - Error payloads are mostly consistent
  - Full schema-backed normalization is not in place yet

- `[x]` Ticket C10: Register new routers in `app/main.py`

## Milestone D: Realtime / SSE

Goal: live sync across web clients and SMS updates.

- `[~]` Ticket D1: Add SSE router
  - `GET /api/events/stream` exists
  - Token validation is implemented via query param
  - `last_event_id` replay is supported via query param
  - Standard `Last-Event-ID` header handling is not implemented yet

- `[~]` Ticket D2: Define event types and payload schema
  - Implemented: `item.updated`, `item.deleted`, `item.duplicate_resolved`, `category.created`, `category.updated`, `category.deleted`, `trip.started`, `trip.completed`, `list.replaced`
  - Not implemented yet: `item.created`, `item.pending_duplicate`, `snapshot.required`

- `[~]` Ticket D3: Emit events from service-layer mutations
  - Implemented for item update/delete/toggle, category create/rename/delete, trip start/complete, duplicate resolution, list replacement
  - Not implemented yet for item create and pending duplicate creation

- `[ ]` Ticket D4: Integrate SMS-originated changes with event emission
  - Existing SMS flow has not been explicitly wired and verified yet

- `[~]` Ticket D5: Add reconnect and replay behavior
  - Basic replay from `last_event_id` is in place
  - Automatic reconnect strategy and `snapshot.required` handling are not implemented yet

## Milestone E: Frontend Foundation

Goal: get the shared app shell running.

- `[x]` Ticket E1: Scaffold frontend app
  - Choose React + Vite
  - Set up build output for FastAPI serving

- `[~]` Ticket E2: Add app bootstrap and routing
  - App bootstrap exists
  - Direct-open shared-link routing is not implemented yet

- `[ ]` Ticket E3: Create API client module
  - Token header injection
  - JSON parsing
  - Error normalization

- `[ ]` Ticket E4: Create app state store
  - State currently lives directly in `App.jsx`

- `[x]` Ticket E5: Load initial snapshot from `/api/app-state`

- `[~]` Ticket E6: Establish SSE subscription
  - Incoming item events are applied to local state
  - Reconnect handling is not implemented yet

- `[x]` Ticket E7: Build mobile-first shell
  - Header and list container
  - Empty-state prompt
  - Basic error state

## Milestone F: Item Workflow UI

Goal: deliver useful daily list management.

- `[~]` Ticket F1: Build add-item form
  - Required name is implemented
  - Quantity and notes are implemented
  - Category input is not implemented yet

- `[ ]` Ticket F2: Add optimistic item creation
  - Show temp quantity `1`
  - Show temp category `Uncategorized`
  - Reconcile with server response

- `[x]` Ticket F3: Build inline item row editing
  - Name
  - Quantity
  - Category
  - Notes

- `[ ]` Ticket F4: Add autosave behavior
  - Current UI uses an explicit save action
  - Error and retry UI is still minimal

- `[x]` Ticket F5: Add immediate delete action
  - No confirmation
  - No undo

- `[x]` Ticket F6: Render purchased state
  - Checked box
  - Strikethrough text

- `[~]` Ticket F7: Handle active-trip `New` badge
  - Badge rendering is implemented
  - Clearing on check is supported
  - Create-time `new_during_trip` population is not implemented yet

## Milestone G: Category UI

Goal: enable organization workflows.

- `[x]` Ticket G1: Build category section component
  - Section header
  - Ordered rendering from backend

- `[ ]` Ticket G2: Create category flow
  - Inline create UI
  - Server-backed creation

- `[ ]` Ticket G3: Rename category flow
  - Inline rename
  - Auto-refresh affected items

- `[ ]` Ticket G4: Delete category flow
  - Confirmation dialog
  - Disabled state when category contains items
  - Explanatory message

- `[x]` Ticket G5: Item reassignment UX
  - Category selector in inline item editor

## Milestone H: Trip Workflow UI

Goal: support shopping mode end-to-end.

- `[x]` Ticket H1: Build trip banner
  - Persistent when active
  - Show start time only

- `[x]` Ticket H2: Add start-trip action
  - Blocked when list is empty

- `[x]` Ticket H3: Enable check and uncheck during trip
  - Only active during current trip
  - Immediate visual update

- `[x]` Ticket H4: Build finish-trip prepare flow
  - Fetch unchecked items
  - Launch review modal

- `[~]` Ticket H5: Build item-by-item carryover modal
  - Carry and skip choices exist
  - Full multi-item step-through UX is not implemented yet

- `[x]` Ticket H6: Complete finish-trip flow
  - Submit carryover decisions
  - Refresh to new active list state

## Milestone I: Conflict + Duplicate UX

Goal: handle collaborative edge cases safely.

- `[~]` Ticket I1: Duplicate modal UI
  - Show pending item and existing item
  - `keep separate` and `cancel` are implemented
  - `merge` is not implemented yet

- `[x]` Ticket I2: Duplicate create reconciliation
  - Handle `202` response on add-item
  - Keep UI stable while awaiting user decision

- `[x]` Ticket I3: Conflict modal UI
  - Show client version
  - Show server version
  - Allow `keep server` or `overwrite with mine`

- `[x]` Ticket I4: Stale edit detection in client
  - Preserve typing
  - Only interrupt after save attempt resolves as conflict

- `[ ]` Ticket I5: Category conflict handling
  - Same modal pattern for category rename and edit conflicts

## Milestone J: Tests + Hardening

Goal: make the feature ship-ready.

- `[x]` Ticket J1: Add service tests for item mutation rules
- `[x]` Ticket J2: Add service tests for category deletion and rename rules
- `[x]` Ticket J3: Add service tests for trip start, finish, and carryover
- `[~]` Ticket J4: Add service tests for version conflicts
  - Conflict behavior is covered at the API level
  - Dedicated service-level conflict tests are not in place yet
- `[x]` Ticket J5: Add API tests for all new endpoints currently implemented
- `[x]` Ticket J6: Add SSE tests for event replay and stream output
- `[x]` Ticket J7: Add frontend tests for optimistic add, edit, and delete flows
- `[x]` Ticket J8: Add frontend tests for duplicate and conflict modals
- `[ ]` Ticket J9: Add integration test for SMS-to-web sync
- `[~]` Ticket J10: Update docs
  - `docs/web/` planning and delivery docs are updated
  - Existing architecture, dataflow, database, and testing docs have not been updated yet

## Suggested Priority Order

1. A1-A7
2. B1-B10
3. C1-C10
4. E1-E7
5. F1-F7
6. D1-D5
7. H1-H6
8. G1-G5
9. I1-I5
10. J1-J10

## Recommended First Sprint

A realistic first sprint:

- A1-A7
- B1-B5
- C1-C5
- E1-E5
- F1-F3

That should get the project to a basic web list with add, edit, and delete against real APIs, even before live sync and trip management land.
