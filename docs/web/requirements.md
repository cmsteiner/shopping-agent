# Web Interface Requirements

## Overview

Build a mobile-first web interface for the shared household shopping list. The interface is designed for Chris and Donna to manage the current active list and the current shopping trip from phone browsers.

## Product Goal

The web interface should allow users to:

1. Add and remove items from the current list.
2. Edit item details inline.
3. Start, run, and finish the current shopping trip.
4. Stay in sync with backend and SMS-driven changes in near real time.

## Users

- Chris and Donna use the same shared interface.
- There is no per-user identity in v1.
- Anyone with the shared private link can use the app.

## Access Model

- One shared private link for both Chris and Donna.
- No authentication in v1.
- No login, logout, profile, settings, or account screens.
- Opening the shared link lands directly on the current list.

## Platform

- Mobile web app only
- Primarily optimized for phones
- Safari and Chrome are sufficient for v1
- No PWA/installable support required

## List Scope

- The app supports only one shared current active list.
- No multiple households or multiple lists in v1.
- No past completed lists or trip history in v1.

## Current List Screen

- Show the current active list directly.
- If the list is empty, show an empty list with an add-item prompt.
- Group items by category.
- Categories are ordered as provided by the backend.
- Items within each category are ordered alphabetically.
- Purchased items stay mixed into alphabetical order.

## Item Display

Each item should support:

- item name
- quantity
- category assignment
- optional notes
- purchased state
- `New` badge when added during an active trip

Purchased items should display with:

- a checked checkbox
- strikethrough text

## Item Add

Users can add items at any time, including during an active shopping trip.

Add-item behavior:

- Structured fields
- Required: item name
- Optional: quantity
- Optional: category
- Optional: notes

If quantity is omitted:

- Show temporary quantity `1` immediately.
- Backend may later update it.

If category is omitted:

- Show temporary category `Uncategorized` immediately.
- Backend may later update it.

The UI should show the new item immediately rather than waiting for backend enrichment.

## Item Edit

Users can edit at any time, including during an active shopping trip:

- text
- quantity
- category
- notes

Editing behavior:

- inline editing on the list screen
- auto-save
- no separate edit screen

## Item Remove

- Users can remove items at any time, including during an active trip.
- Removal happens immediately.
- No confirmation.
- No undo in v1.

## Category Management

Users can:

- create new categories
- rename categories
- assign and reassign items to categories
- delete categories

Rules:

- Category updates are allowed during an active shopping trip.
- Renaming a category applies immediately to all items in that category.
- Deleting a category requires confirmation.
- If a category still has items, delete is disabled and the UI shows a message that items must be moved first.

## Shopping Trip

Users can:

- start a trip
- check items while shopping
- uncheck items while shopping
- finish a trip

Rules:

- A trip can only start when the list has at least one item.
- Both users can interact with the same active trip at the same time.
- Either person can finish the trip.
- Purchased items remain editable during an active trip.

Trip UI:

- Show a persistent `shopping trip in progress` banner.
- Banner shows start time only.
- Banner does not show who started the trip.

## New Items During Active Trip

If an item is added during an active trip:

- show a `New` badge
- keep the badge until the item is checked off

## Trip Completion

On completion:

- Backend archives the entire list.
- If unchecked items remain, allow finishing the trip anyway.
- Prompt the user item by item to decide whether each unchecked item should be carried into the new list.
- Support reviewing every unchecked item regardless of count.

## Live Updates

The web interface should stay in sync live for:

- changes made by another web client
- changes made through SMS/backend flows
- backend updates to placeholder values
- trip state changes
- category changes

Manual refresh should not be required for normal updates.

## Conflict Handling

If two users edit the same item or category at nearly the same time:

- let the current user finish typing first
- then show a conflict warning
- show both versions
- let the user choose which version to keep

## Duplicate Item Validation

If a new item appears to duplicate an existing item:

- backend flags the duplicate
- UI shows a modal comparing the new and existing items
- choices are:
  - `merge`
  - `keep separate`
  - `cancel`

## Notifications and Error Handling

In v1:

- no browser push notifications
- no success toasts
- show messages only for errors, conflicts, and trip-completion carryover decisions
- assume online use
- if save fails, show a simple error/retry state

## Out of Scope for v1

- authentication
- multiple households
- multiple lists
- list history or trip history
- search
- filters
- manual item ordering
- offline support
- PWA behavior
- user-change history display
- settings/profile pages
