# Build Checklist

## Milestone A: Schema + Models

Goal: establish the database foundation.

- Ticket A1: Add `categories` table via Alembic
  - Create columns: `id`, `name`, `normalized_name`, `sort_order`, `created_at`, `updated_at`, `version`
  - Add unique constraint on `normalized_name`

- Ticket A2: Extend `items` table for web state
  - Add `notes`
  - Add `category_id`
  - Add `is_purchased`
  - Add `purchased_at`
  - Add `new_during_trip`
  - Add `updated_at`
  - Add `version`

- Ticket A3: Add `shopping_trips` table via Alembic
  - Create columns: `id`, `list_id`, `status`, `started_at`, `completed_at`, `version`

- Ticket A4: Add `list_events` table via Alembic
  - Create columns: `id`, `list_id`, `event_type`, `entity_type`, `entity_id`, `payload_json`, `created_at`

- Ticket A5: Backfill categories and item category references
  - Seed canonical categories
  - Insert any existing distinct item category strings not already present
  - Populate `items.category_id`
  - Set `items.updated_at = items.created_at`
  - Set `version = 1` on backfilled rows

- Ticket A6: Update SQLAlchemy models
  - Add new ORM models for `Category`, `ShoppingTrip`, `ListEvent`
  - Extend `Item` and `ShoppingList`
  - Wire relationships in `app/models/__init__.py`

- Ticket A7: Add migration test coverage
  - Verify upgrade on empty DB
  - Verify upgrade on populated DB
  - Verify app startup after migration

## Milestone B: Core Services

Goal: make the backend capable of the new domain behavior.

- Ticket B1: Add category lookup/create helpers
  - Resolve category names to IDs
  - Normalize names consistently
  - Preserve backend ordering

- Ticket B2: Refactor `item_service.add_items()`
  - Support `notes`
  - Support `category_id`
  - Keep `category` text synchronized during transition
  - Set `new_during_trip` when active trip exists
  - Stamp `updated_at` and `version`

- Ticket B3: Add `item_service.update_item()`
  - Support inline updates for `name`, `quantity`, `unit`, `notes`, `category_id`
  - Enforce optimistic concurrency with `base_version`

- Ticket B4: Add `item_service.delete_item()`
  - Delete immediately
  - Optional `base_version` enforcement

- Ticket B5: Add `item_service.toggle_purchased()`
  - Allow only during active trip
  - Set `is_purchased`
  - Set and clear `purchased_at`
  - Clear `new_during_trip` when checked

- Ticket B6: Create `category_service.py`
  - `create_category`
  - `rename_category`
  - `delete_category`
  - Delete blocked when category still has items

- Ticket B7: Create `trip_service.py`
  - `start_trip`
  - `get_active_trip`
  - `prepare_finish_trip`
  - `complete_finish_trip`

- Ticket B8: Create `conflict_service.py`
  - Compare `base_version`
  - Build standardized `409` payloads
  - Support whole-record overwrite resolution

- Ticket B9: Create `realtime_service.py`
  - Append `list_events`
  - Query events after event ID
  - Serialize event payloads for SSE

- Ticket B10: Update `list_service.py` for trip completion
  - Archive current list
  - Create new active list
  - Recreate carried-over items

## Milestone C: API Schemas + Routing

Goal: expose the agreed contract cleanly.

- Ticket C1: Add shared-token config
  - Add `WEB_SHARED_TOKEN` to config
  - Document env var in `.env.example`

- Ticket C2: Add token validation dependency
  - Read `X-App-Token`
  - Return `403` on invalid or missing token

- Ticket C3: Create `app/schemas/web.py`
  - Request models
  - Response models
  - Error models
  - Conflict models

- Ticket C4: Add `GET /api/app-state`
  - Return full snapshot
  - Include list, trip, categories, grouped items, pending prompts

- Ticket C5: Add item endpoints
  - `POST /api/items`
  - `PATCH /api/items/{id}`
  - `DELETE /api/items/{id}`
  - `POST /api/items/{id}/toggle-purchased`

- Ticket C6: Add category endpoints
  - `POST /api/categories`
  - `PATCH /api/categories/{id}`
  - `DELETE /api/categories/{id}`

- Ticket C7: Add trip endpoints
  - `POST /api/trips/start`
  - `POST /api/trips/{id}/finish/prepare`
  - `POST /api/trips/{id}/finish/complete`

- Ticket C8: Add duplicate and conflict resolution endpoints
  - `POST /api/duplicates/{pending_confirmation_id}/resolve`
  - `POST /api/conflicts/resolve`

- Ticket C9: Standardize error handling
  - `403`, `404`, `409`, `422`
  - Consistent JSON error envelope

- Ticket C10: Register new routers in `app/main.py`

## Milestone D: Realtime / SSE

Goal: live sync across web clients and SMS updates.

- Ticket D1: Add SSE router
  - `GET /api/events/stream`
  - Validate token
  - Support `Last-Event-ID`

- Ticket D2: Define event types and payload schema
  - `item.created`
  - `item.updated`
  - `item.deleted`
  - `item.pending_duplicate`
  - `item.duplicate_resolved`
  - `category.created`
  - `category.updated`
  - `category.deleted`
  - `trip.started`
  - `trip.completed`
  - `list.replaced`
  - `snapshot.required`

- Ticket D3: Emit events from service-layer mutations
  - Item create/update/delete
  - Category create/rename/delete
  - Trip start/complete
  - Duplicate resolution
  - List replacement

- Ticket D4: Integrate SMS-originated changes with event emission
  - Ensure existing SMS service path also emits list events
  - No request-handler blocking changes

- Ticket D5: Add reconnect and replay behavior
  - Replay from last seen event
  - Emit `snapshot.required` on replay gaps

## Milestone E: Frontend Foundation

Goal: get the shared app shell running.

- Ticket E1: Scaffold frontend app
  - Choose React + Vite
  - Set up build output for FastAPI serving

- Ticket E2: Add app bootstrap and routing
  - Shared token route
  - Direct open to list screen

- Ticket E3: Create API client module
  - Token header injection
  - JSON parsing
  - Error normalization

- Ticket E4: Create app state store
  - List
  - Trip
  - Categories
  - Items
  - Pending modals
  - Connection status

- Ticket E5: Load initial snapshot from `/api/app-state`

- Ticket E6: Establish SSE subscription
  - Apply incoming events to local state
  - Handle reconnects

- Ticket E7: Build mobile-first shell
  - Header and list container
  - Empty-state prompt
  - Basic error state

## Milestone F: Item Workflow UI

Goal: deliver useful daily list management.

- Ticket F1: Build add-item form
  - Required name
  - Optional quantity
  - Optional category
  - Optional notes

- Ticket F2: Add optimistic item creation
  - Show temp quantity `1`
  - Show temp category `Uncategorized`
  - Reconcile with server response

- Ticket F3: Build inline item row editing
  - Name
  - Quantity
  - Category
  - Notes

- Ticket F4: Add autosave behavior
  - Save on blur/change as designed
  - Show simple error/retry state on failure

- Ticket F5: Add immediate delete action
  - No confirmation
  - No undo

- Ticket F6: Render purchased state
  - Checked box
  - Strikethrough text

- Ticket F7: Handle active-trip `New` badge
  - Show for items added during trip
  - Remove when checked

## Milestone G: Category UI

Goal: enable organization workflows.

- Ticket G1: Build category section component
  - Section header
  - Ordered rendering from backend

- Ticket G2: Create category flow
  - Inline create UI
  - Server-backed creation

- Ticket G3: Rename category flow
  - Inline rename
  - Auto-refresh affected items

- Ticket G4: Delete category flow
  - Confirmation dialog
  - Disabled state when category contains items
  - Explanatory message

- Ticket G5: Item reassignment UX
  - Category selector in inline item editor

## Milestone H: Trip Workflow UI

Goal: support shopping mode end-to-end.

- Ticket H1: Build trip banner
  - Persistent when active
  - Show start time only

- Ticket H2: Add start-trip action
  - Disable or block when list is empty

- Ticket H3: Enable check and uncheck during trip
  - Only active during current trip
  - Immediate visual update

- Ticket H4: Build finish-trip prepare flow
  - Fetch unchecked items
  - Launch review modal

- Ticket H5: Build item-by-item carryover modal
  - Step through every unchecked item
  - Record carry/skip decision

- Ticket H6: Complete finish-trip flow
  - Submit carryover decisions
  - Refresh to new active list state

## Milestone I: Conflict + Duplicate UX

Goal: handle collaborative edge cases safely.

- Ticket I1: Duplicate modal UI
  - Show pending item and existing item
  - Actions: `merge`, `keep separate`, `cancel`

- Ticket I2: Duplicate create reconciliation
  - Handle `202` response on add-item
  - Keep UI stable while awaiting user decision

- Ticket I3: Conflict modal UI
  - Show client version
  - Show server version
  - Allow `keep server` or `overwrite with mine`

- Ticket I4: Stale edit detection in client
  - Preserve typing
  - Only interrupt after save attempt resolves as conflict

- Ticket I5: Category conflict handling
  - Same modal pattern for category rename/edit conflicts

## Milestone J: Tests + Hardening

Goal: make the feature ship-ready.

- Ticket J1: Add service tests for item mutation rules
- Ticket J2: Add service tests for category deletion and rename rules
- Ticket J3: Add service tests for trip start, finish, and carryover
- Ticket J4: Add service tests for version conflicts
- Ticket J5: Add API tests for all new endpoints
- Ticket J6: Add SSE tests for event replay and stream output
- Ticket J7: Add frontend tests for optimistic add/edit/delete
- Ticket J8: Add frontend tests for duplicate and conflict modals
- Ticket J9: Add integration test for SMS-to-web sync
- Ticket J10: Update docs
  - architecture
  - dataflow
  - database
  - testing

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

That should get the project to a basic web list with add/edit/delete against real APIs, even before live sync and trip management land.
