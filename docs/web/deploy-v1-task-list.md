# Deploy V1 Task List

Status legend:
- `[ ]` Not started
- `[~]` In progress
- `[x]` Complete

This file tracks only the remaining work required to deploy the agreed v1 web experience, not every possible cleanup item.

## Task 1: Serve the web app from FastAPI through a shared-link route

Status: `[x]`

Goal:
- Make the React app reachable in production from the FastAPI service.

Scope:
- Add a shared-link route such as `/app/{token}`
- Serve built frontend assets from the backend
- Return the SPA shell for valid shared-link requests
- Keep API token behavior aligned with the shared-link access model
- Add backend tests for the new route and asset serving behavior

Deployment outcome:
- A deployed FastAPI instance can directly serve the web UI without a separate frontend host.

## Task 2: Complete duplicate-item creation and merge resolution end to end

Status: `[x]`

Goal:
- Make duplicate detection and resolution production-ready.

Scope:
- Return pending-duplicate responses from `POST /api/items` when appropriate
- Emit pending-duplicate realtime events
- Implement duplicate `merge` resolution in the backend
- Add frontend handling for `merge`
- Add backend and frontend tests for duplicate create and merge flows

Deployment outcome:
- Duplicate adds behave correctly and no longer bypass the pending-confirmation workflow.

## Task 3: Finish category management for v1

Status: `[x]`

Goal:
- Complete the remaining category workflows promised in the v1 spec.

Scope:
- Add category rename UI
- Add category conflict handling
- Tighten delete UX to match the confirmed behavior
- Add tests for rename and category conflict flows

Deployment outcome:
- Category create, rename, delete, and reassignment are all available in the deployed app.

## Task 4: Finish live sync for the shared app

Status: `[~]`

Goal:
- Make the web app feel fully shared and stay consistent across clients.

Scope:
- Extend frontend SSE handling for category, trip, list-replaced, and duplicate-resolution events
- Improve replay/reconnect handling
- Add missing backend event payloads where needed
- Add tests for the new event types

Deployment outcome:
- Web users see important shared-state changes live without refresh.

## Task 5: Add deployment and production hardening for v1

Status: `[ ]`

Goal:
- Close the remaining gaps between “feature-complete enough” and “safe to deploy.”

Scope:
- Add or update docs for build/deploy steps
- Verify frontend build integration
- Add an end-to-end smoke test path for deployed app boot and core API use
- Update architecture/dataflow/testing docs where the web channel changed the system
- Run final verification for backend and frontend suites

Deployment outcome:
- The repo contains the code, configuration, and documentation needed to deploy the v1 web app confidently.
