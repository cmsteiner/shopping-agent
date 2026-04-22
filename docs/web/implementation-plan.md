# Implementation Plan

## Overview

This plan is ordered to keep the app working at every step and minimize risk to the existing SMS flow.

## Phase 1: Schema Foundation

Goal: add the data model needed for the web app without changing behavior yet.

Tasks:

- add Alembic migration for `categories`
- add Alembic migration for new `items` columns
- add Alembic migration for `shopping_trips`
- add Alembic migration for `list_events`
- backfill category rows from canonical categories plus existing item category strings
- backfill `items.category_id`
- backfill `items.updated_at` from `created_at`
- backfill `version=1` everywhere needed

Files:

- `alembic/`
- `app/models/item.py`
- new `app/models/category.py`
- new `app/models/shopping_trip.py`
- new `app/models/list_event.py`
- `app/models/shopping_list.py`
- `app/models/__init__.py`

Exit criteria:

- migrations run cleanly on empty and existing DBs
- existing SMS app still starts
- existing tests still pass or only fail for expected model updates

## Phase 2: Service-Layer Refactor

Goal: make the backend capable of the new behaviors before exposing web endpoints.

Tasks:

- extend `item_service` for create/update/delete/toggle purchased
- create `category_service`
- create `trip_service`
- create `realtime_service`
- create `conflict_service`
- update `list_service` to cooperate with trip completion and list replacement
- ensure every mutation increments `version` and updates `updated_at`
- ensure every mutation emits a `list_event`
- keep `items.category` and `items.category_id` synchronized during v1

Files:

- `app/services/item_service.py`
- `app/services/list_service.py`
- new `app/services/category_service.py`
- new `app/services/trip_service.py`
- new `app/services/realtime_service.py`
- new `app/services/conflict_service.py`

Exit criteria:

- service methods exist for all API actions
- service-layer tests cover trip rules, duplicate handling, and version conflicts
- SMS-originated mutations can emit events without changing webhook timing behavior

## Phase 3: Web API Surface

Goal: add the JSON contract on top of the new services.

Tasks:

- add Pydantic request/response schemas
- add token validation dependency
- implement `GET /api/app-state`
- implement item endpoints
- implement category endpoints
- implement trip endpoints
- implement duplicate resolution endpoint
- implement conflict resolution endpoint
- implement consistent error format
- wire routers into FastAPI app

Files:

- new `app/schemas/web.py`
- new `app/routers/api.py`
- `app/main.py`
- possibly `app/config.py` for `WEB_SHARED_TOKEN`

Exit criteria:

- all documented endpoints return the agreed shapes
- invalid token returns `403`
- stale writes return `409`
- business-rule errors return `422`

## Phase 4: Real-Time Sync

Goal: keep the web UI live-updated from both web and SMS actions.

Tasks:

- add SSE router
- implement event replay by `Last-Event-ID`
- add reconnect-safe stream format
- emit `snapshot.required` when replay gap is too large
- verify SMS-driven item changes show up live in connected web clients

Files:

- new `app/routers/realtime.py`
- `app/services/realtime_service.py`

Exit criteria:

- browser can subscribe and receive ordered events
- reconnect works
- both web and SMS mutations appear on stream

## Phase 5: Frontend Skeleton

Goal: get a usable app shell on screen fast.

Tasks:

- scaffold frontend app
- add shared token route
- load initial snapshot from `/api/app-state`
- render empty state
- render category-grouped list
- render trip banner
- establish SSE connection
- add mobile-first layout and baseline styles

Files:

- new `frontend/` app or static asset structure
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/events.ts`
- `frontend/src/store.ts`

Exit criteria:

- private shared link opens the app
- list renders from backend data
- live updates patch the UI

## Phase 6: Core Item UX

Goal: deliver the highest-value daily workflow first.

Tasks:

- add structured add-item form
- implement optimistic add with placeholders
- render `Uncategorized` and quantity `1` immediately when omitted
- add inline editing with autosave
- add immediate delete
- add purchased toggle during active trip
- render checked state and strikethrough
- show save error/retry state

Files:

- `frontend/src/components/ListScreen.tsx`
- `frontend/src/components/ItemRow.tsx`
- `frontend/src/components/AddItemForm.tsx`

Exit criteria:

- add/edit/delete/check flows work smoothly on phone
- optimistic UI reconciles correctly with server responses
- no page refresh required

## Phase 7: Category Management

Goal: complete list organization features.

Tasks:

- create category UI
- inline rename category
- category reassignment in item rows
- delete category confirmation
- disable delete for non-empty categories with message
- reflect backend ordering

Files:

- `frontend/src/components/CategorySection.tsx`
- optionally `frontend/src/components/CategoryEditor.tsx`

Exit criteria:

- categories can be created, renamed, and deleted under the agreed rules
- category conflicts return and display correctly

## Phase 8: Trip Workflow

Goal: make the shopping trip flow complete end-to-end.

Tasks:

- implement start trip action
- render persistent active-trip banner with start time
- enable check/uncheck only during active trip
- mark newly added items with `New`
- clear `New` on check
- implement finish-trip prepare flow
- implement item-by-item carryover modal
- complete trip and refresh into new active list

Files:

- `frontend/src/components/TripBanner.tsx`
- `frontend/src/components/FinishTripModal.tsx`
- `app/services/trip_service.py`

Exit criteria:

- trip start is blocked on empty list
- finish flow works with any number of unchecked items
- completion archives old list and creates the new one correctly

## Phase 9: Duplicate + Conflict Flows

Goal: handle the tricky collaborative cases cleanly.

Tasks:

- duplicate modal with `merge`, `keep separate`, `cancel`
- detect stale inline edits via `base_version`
- show whole-record conflict chooser after user finishes typing
- implement conflict resolution calls
- handle SSE updates while an item is being edited without interrupting typing

Files:

- `frontend/src/components/DuplicateModal.tsx`
- `frontend/src/components/ConflictModal.tsx`
- `app/services/conflict_service.py`

Exit criteria:

- concurrent edits produce user-visible resolution, not silent overwrites
- duplicate adds use modal-driven resolution

## Phase 10: Hardening and Rollout

Goal: make the feature safe to ship.

Tasks:

- add API integration tests
- add service tests for conflict/trip/category rules
- add frontend tests for optimistic updates and modal flows
- test against SMS changes arriving during web use
- confirm webhook behavior remains immediate and unchanged
- add deployment config for frontend assets and shared token
- document the web channel in the docs set

Files:

- `app/tests/`
- `docs/architecture.md`
- `docs/dataflow.md`
- `docs/database.md`
- `docs/testing.md`

Exit criteria:

- web and SMS coexist reliably
- no blocking AI work introduced into request handlers
- core mobile workflows verified

## Recommended Build Order

1. Phase 1
2. Phase 2
3. Phase 3 with `app-state` and item endpoints
4. Phase 5
5. Phase 6
6. Phase 4
7. Phase 8
8. Phase 7
9. Phase 9
10. Phase 10

This gets a basic shared list working early, then layers in live sync and more complex trip/conflict behavior.

## Suggested Milestone Breakdown

- Milestone A: schema + services
- Milestone B: snapshot API + item CRUD
- Milestone C: frontend list UI
- Milestone D: SSE live sync
- Milestone E: trip workflow
- Milestone F: categories
- Milestone G: conflicts and duplicates
- Milestone H: hardening and docs
