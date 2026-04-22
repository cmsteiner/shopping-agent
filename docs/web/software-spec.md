# Software Spec

## Overview

Build a mobile-first web interface for the existing shopping-agent system so Chris and Donna can manage the shared current shopping list and the active shopping trip from a phone browser. In v1, the app is a single shared experience accessed via one private link, with no login or account management.

## Product Goal

The interface should make it easy to:

1. Add and remove items from the current list.
2. Edit item details inline.
3. Start, run, and finish the current shopping trip.
4. Stay in sync with backend and SMS-driven changes in near real time.

## Users

The product serves a shared household workflow for Chris and Donna.
There is no per-user identity in v1.
The app behaves as a single shared interface for anyone with the shared private link.

## Scope

In scope:

- View the current active list
- Add items
- Remove items
- Edit item text, quantity, category, and notes inline
- Group items by category
- Create, rename, and delete categories
- Start a shopping trip
- Check and uncheck items during a trip
- Finish a shopping trip
- Resolve edit conflicts
- Handle duplicate-item validation from the backend
- Reflect backend/SMS changes live

Out of scope for v1:

- Authentication and authorization
- Multiple households or multiple lists
- Past trip/history views
- Search and filtering
- Manual item reordering
- Push notifications
- Offline-first behavior
- Accessibility-specific compliance requirements beyond normal browser behavior
- In-app management of recovery contact details
- Profile/settings pages

## Platform

- Mobile web app only
- Optimized primarily for phone use
- Supported browsers: Safari and Chrome
- No PWA or installable app behavior required

## Navigation

The shared private link opens directly to the current list screen.
There are no separate home, profile, settings, or history screens in v1.

## Shared-Link Access Model

The application is accessed through one shared private URL used by both Chris and Donna.
There is no login.
Anyone with the URL can access and use the interface.
The system should treat this as acceptable v1 behavior.

## Core Data Assumptions

The UI operates on:

- one current active list
- zero or one active shopping trip associated with that list
- items with at least:
  - name
  - quantity
  - category
  - optional notes
  - purchased/checked state during an active trip
  - `new during active trip` indicator state
- categories supplied and ordered by the backend

## Functional Requirements

### 1. Current List Screen

The main screen must:

- display the current active list
- show an empty-state prompt when the list has no items
- group items by category
- render category groups in backend-provided order
- render items alphabetically within each category
- keep purchased items mixed into alphabetical order rather than separating them

If there is no active list content, the screen shows:

- an empty list state
- a clear add-item prompt

### 2. Item Display

Each item row must support display of:

- item name
- quantity
- category context
- optional notes
- purchased state
- `New` badge when applicable

Purchased visual treatment:

- checked checkbox
- strikethrough text

### 3. Add Item

Users must be able to add items at any time, including during an active shopping trip.

Add-item form behavior:

- structured fields
- required: item name
- optional: quantity
- optional: category
- optional: notes

If quantity is left blank:

- UI shows temporary quantity `1` immediately

If category is left blank:

- UI shows temporary category `Uncategorized` immediately

The UI must:

- show the newly added item immediately without waiting for backend enrichment
- update the item when backend-supplied quantity/category arrive

If a trip is active when a new item is added:

- the item must receive a `New` badge

### 4. Edit Item Inline

Users must be able to edit inline:

- item text
- quantity
- category
- notes

Behavior:

- inline editing only, no separate edit page
- edits auto-save
- edits are allowed even during an active trip
- purchased items may still be edited during an active trip

If save fails:

- show a simple error state
- provide retry behavior

No success toast is required.

### 5. Remove Item

Users must be able to remove items at any time, including during an active trip.

Behavior:

- deletion happens immediately
- no confirmation prompt
- no undo

### 6. Category Management

Users must be able to:

- create categories
- rename categories
- reassign items to categories
- delete categories

Behavior:

- category changes are allowed even during an active trip
- renaming a category applies immediately to all items currently in that category
- categories are displayed in backend-provided order

Delete-category rules:

- deletion requires confirmation
- if the category still contains items, delete must be disabled
- the UI must show a message telling the user items must be moved first
- users are not offered automatic move-on-delete in v1

### 7. Active Shopping Trip

Users must be able to:

- start a trip
- check items while shopping
- uncheck items while shopping
- finish a trip

Start-trip rules:

- trip can only be started if there is at least one item on the current list

During an active trip:

- both users can interact with the same trip at the same time
- item checking is reversible
- item editing and category updates remain allowed

Active-trip UI:

- persistent banner indicating shopping trip in progress
- banner shows start time only
- banner does not show who started the trip

### 8. New Items During Active Trip

If an item is added while a trip is active:

- it must display a `New` badge so the shopper notices it

Badge lifecycle:

- the `New` badge disappears when the item is checked off
- it does not disappear simply because someone viewed the item

### 9. Finish Trip

When the trip is finished:

- backend archives the entire current list

If unchecked items remain:

- finishing is still allowed
- UI must prompt the user item by item to decide whether each unchecked item should be carried into the new list
- the UI must support reviewing every unchecked item regardless of count

Either person may finish the trip.

### 10. Real-Time Sync

The interface must stay in sync with:

- changes made by another web client
- changes made through SMS flows and backend processing

Expectation:

- updates appear live without requiring manual refresh

This includes live updates for:

- item add/edit/delete
- category changes
- trip state changes
- check/uncheck events
- backend-enriched placeholder values
- duplicate/conflict outcomes where applicable

### 11. Conflict Handling

If two users edit the same item or category at nearly the same time:

- the user currently typing should be allowed to finish typing first
- after that, the UI must show a conflict warning
- the UI must present both versions
- the user must choose which version to keep

This applies to:

- item edits
- category changes

The spec should assume backend support for detecting version conflicts or stale writes.

### 12. Duplicate Item Validation

If a newly added item appears to duplicate an existing item:

- backend flags the duplicate conflict
- UI immediately presents a validation modal

Modal options:

- merge
- keep separate
- cancel

Expected behavior:

- user must explicitly choose one of those outcomes before duplicate handling is finalized

### 13. Error Handling

The app may assume users are online in v1.
If a save or action fails:

- show a simple error state/message
- provide a retry path where relevant

The app should show UI messages only for:

- errors
- conflicts
- trip-completion carryover decisions

No general success messages or success toasts are required.

## Non-Functional Requirements

- mobile-first layout and interactions
- fast perceived responsiveness for add/edit/check flows
- immediate webhook constraints remain unchanged in backend architecture
- web UI must integrate without breaking existing SMS-driven operation
- UI should tolerate concurrent usage by two people
- session/auth persistence is irrelevant in v1 because there is no authentication

## User Stories

1. As a household user, I want to open a single shared link and immediately see the current list so I can use the app quickly.
2. As a shopper, I want to add an item with minimal required input so I can capture needs quickly.
3. As a user, I want missing category and quantity to appear with temporary defaults so the list updates instantly.
4. As a user, I want to edit item details inline so I do not need to navigate away from the list.
5. As a shopper, I want to check and uncheck items during a trip so I can track what has been picked up.
6. As a shopper, I want newly added items to be visibly marked during an active trip so I notice them.
7. As a user, I want category management in the same interface so I can keep the list organized.
8. As a user, I want live updates from web and SMS activity so the list stays current without refresh.
9. As a user, I want conflict resolution when simultaneous edits happen so I do not silently lose changes.
10. As a user, I want duplicate-item validation so I can decide whether to merge similar entries.
11. As a shopper, I want to finish a trip even with unchecked items so the workflow does not block me.
12. As a shopper, I want to decide item-by-item which unchecked items carry over so the next list is accurate.

## Acceptance Criteria

### Current List

1. Given the shared app link is opened, when the app loads, then the user lands directly on the current list screen.
2. Given the list is empty, when the screen loads, then an empty-state add-item prompt is shown.
3. Given items exist, when the list is shown, then items are grouped by category and categories are ordered as provided by the backend.
4. Given multiple items exist in a category, when displayed, then they appear in alphabetical order.
5. Given an item is purchased, when displayed, then it shows a checked box and strikethrough.

### Add Item

1. Given the add-item form, when only item name is entered, then the item is created in the UI immediately.
2. Given quantity is omitted, when the item appears immediately, then quantity displays as `1` until backend data updates it.
3. Given category is omitted, when the item appears immediately, then category displays as `Uncategorized` until backend data updates it.
4. Given a trip is active, when a new item is added, then the item displays a `New` badge.

### Edit Item

1. Given an item field is edited inline, when the user changes it, then the system auto-saves without a separate save button.
2. Given an auto-save fails, when the failure is detected, then the UI shows an error and a retry path.
3. Given a purchased item during an active trip, when edited, then the edit is allowed.

### Remove Item

1. Given an item is removed, when the remove action is triggered, then the item is deleted immediately with no confirmation and no undo.

### Categories

1. Given a new category is created, when saved, then it becomes available for assignment.
2. Given a category is renamed, when the rename succeeds, then all items in that category reflect the new name immediately.
3. Given a category contains items, when delete is attempted, then delete is disabled and the UI explains items must be moved first.
4. Given an empty category, when delete is attempted, then the user is asked to confirm deletion.

### Trip Management

1. Given the current list is empty, when the user tries to start a trip, then the action is blocked.
2. Given the list has at least one item, when the user starts a trip, then an active-trip banner appears with the start time.
3. Given an active trip, when a user checks an item, then it remains visible in its category and updates to purchased styling.
4. Given a checked item, when a user unchecks it, then it returns to unpurchased state.
5. Given an item added during an active trip with a `New` badge, when it is checked off, then the `New` badge disappears.
6. Given an active trip with unchecked items, when the user finishes the trip, then the UI prompts item-by-item to carry each unchecked item forward or not.

### Sync

1. Given one client changes an item, when another client is open, then the second client reflects the change live without refresh.
2. Given an item is added or edited through SMS/backend flows, when the web app is open, then the change appears live.

### Conflict Resolution

1. Given two concurrent edits to the same item or category, when a conflict is detected, then the user currently editing is allowed to finish typing before interruption.
2. Given a detected conflict, when the chooser appears, then both versions are displayed and the user must choose one.

### Duplicate Validation

1. Given the backend flags a newly added item as a duplicate, when the app receives that result, then it shows a modal with `merge`, `keep separate`, and `cancel`.

## Open Questions for Technical Design

- What real-time mechanism will be used: polling, SSE, or WebSockets?
- How will conflict detection be represented: version numbers, timestamps, or ETags?
- What exact backend contract will support duplicate-item validation and conflict-choice resolution?
- How should category creation/rename/delete APIs behave relative to existing SMS-driven normalization logic?
- Should `Uncategorized` be a display-only placeholder or a real backend category candidate?

## Recommended Next Step

The next artifact should be a technical design/spec covering:

- frontend architecture and state model
- API/endpoints needed
- real-time sync approach
- conflict/versioning model
- wireframes for the list screen, conflict modal, duplicate modal, and trip completion flow
