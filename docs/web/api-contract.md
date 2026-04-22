# API Contract

## Assumptions

This contract assumes:

- one shared private token for v1
- JSON APIs under `/api`
- SSE for live sync
- optimistic concurrency via `version`
- whole-record conflict resolution for v1

## Conventions

- All requests must include the shared token.
- Simplest option: `X-App-Token: <token>` header on every API request.
- Responses use JSON.
- Timestamps are ISO 8601 UTC strings.
- `409 Conflict` is used for stale writes.
- `422 Unprocessable Entity` is used for validation problems.
- `403 Forbidden` is used for missing/invalid token.

## Common Types

### `AppState`

```json
{
  "list": {
    "id": 12,
    "status": "ACTIVE",
    "version": 5,
    "created_at": "2026-04-22T13:00:00Z"
  },
  "trip": {
    "id": 3,
    "status": "ACTIVE",
    "started_at": "2026-04-22T14:15:00Z",
    "completed_at": null,
    "version": 2
  },
  "categories": [
    {
      "id": 1,
      "name": "Produce",
      "sort_order": 10,
      "version": 3
    }
  ],
  "items_by_category": [
    {
      "category": {
        "id": 1,
        "name": "Produce",
        "sort_order": 10,
        "version": 3
      },
      "items": [
        {
          "id": 101,
          "name": "Apples",
          "quantity": "6.000",
          "unit": null,
          "notes": "Honeycrisp if available",
          "category_id": 1,
          "category_name": "Produce",
          "status": "ACTIVE",
          "is_purchased": false,
          "new_during_trip": false,
          "version": 7,
          "created_at": "2026-04-22T13:05:00Z",
          "updated_at": "2026-04-22T13:12:00Z"
        }
      ]
    }
  ],
  "pending_prompts": {
    "duplicate": null,
    "conflict": null,
    "trip_finish": null
  },
  "server_time": "2026-04-22T14:20:00Z"
}
```

### `ErrorResponse`

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Item name is required."
  }
}
```

### `ConflictResponse`

```json
{
  "error": {
    "code": "version_conflict",
    "message": "This item was updated before your changes were saved."
  },
  "conflict": {
    "entity_type": "item",
    "entity_id": 101,
    "server_version": 8,
    "client_payload": {
      "name": "Green onions",
      "quantity": "2.000",
      "notes": ""
    },
    "server_payload": {
      "id": 101,
      "name": "Scallions",
      "quantity": "1.000",
      "notes": "",
      "category_id": 1,
      "category_name": "Produce",
      "is_purchased": false,
      "new_during_trip": false,
      "version": 8,
      "updated_at": "2026-04-22T14:21:00Z"
    }
  }
}
```

## Auth / Access

All endpoints:

- require `X-App-Token`
- return `403` if invalid

No login/session endpoints in v1.

## 1. Load App State

`GET /api/app-state`

Purpose:

- initial page load
- recovery after reconnect
- fallback full refresh

Response `200`

```json
{
  "list": {
    "id": 12,
    "status": "ACTIVE",
    "version": 5,
    "created_at": "2026-04-22T13:00:00Z"
  },
  "trip": null,
  "categories": [],
  "items_by_category": [],
  "pending_prompts": {
    "duplicate": null,
    "conflict": null,
    "trip_finish": null
  },
  "server_time": "2026-04-22T14:20:00Z"
}
```

## 2. Create Item

`POST /api/items`

Request:

```json
{
  "name": "Milk",
  "quantity": null,
  "unit": null,
  "notes": "2%",
  "category_id": null,
  "client_request_id": "9c49d2d1-8d1f-4bde-9d4d-1b5d3d7b1f2a"
}
```

Notes:

- `name` required
- `quantity`, `category_id`, `notes`, `unit` optional
- `client_request_id` lets the client match optimistic rows

Response `201`

```json
{
  "item": {
    "id": 145,
    "name": "Milk",
    "quantity": "1.000",
    "unit": null,
    "notes": "2%",
    "category_id": 99,
    "category_name": "Dairy",
    "status": "ACTIVE",
    "is_purchased": false,
    "new_during_trip": true,
    "version": 1,
    "created_at": "2026-04-22T14:25:00Z",
    "updated_at": "2026-04-22T14:25:00Z"
  },
  "client_request_id": "9c49d2d1-8d1f-4bde-9d4d-1b5d3d7b1f2a",
  "duplicate_check": {
    "status": "clear"
  }
}
```

Response `202` if duplicate pending:

```json
{
  "pending_duplicate": {
    "pending_confirmation_id": 17,
    "pending_item": {
      "id": 146,
      "name": "Milk",
      "quantity": "1.000",
      "unit": null,
      "notes": "2%",
      "category_id": 99,
      "category_name": "Dairy",
      "status": "PENDING",
      "is_purchased": false,
      "new_during_trip": true,
      "version": 1,
      "created_at": "2026-04-22T14:25:00Z",
      "updated_at": "2026-04-22T14:25:00Z"
    },
    "existing_item": {
      "id": 88,
      "name": "Milk",
      "quantity": "1.000",
      "unit": "gal",
      "notes": "",
      "category_id": 99,
      "category_name": "Dairy",
      "status": "ACTIVE",
      "is_purchased": false,
      "new_during_trip": false,
      "version": 3,
      "created_at": "2026-04-22T13:10:00Z",
      "updated_at": "2026-04-22T13:10:00Z"
    },
    "options": ["merge", "keep_separate", "cancel"]
  },
  "client_request_id": "9c49d2d1-8d1f-4bde-9d4d-1b5d3d7b1f2a"
}
```

## 3. Update Item

`PATCH /api/items/{item_id}`

Request:

```json
{
  "base_version": 7,
  "name": "Apples",
  "quantity": "8.000",
  "notes": "Honeycrisp if available",
  "category_id": 1
}
```

Rules:

- any subset of editable fields allowed
- editable: `name`, `quantity`, `unit`, `notes`, `category_id`

Response `200`

```json
{
  "item": {
    "id": 101,
    "name": "Apples",
    "quantity": "8.000",
    "unit": null,
    "notes": "Honeycrisp if available",
    "category_id": 1,
    "category_name": "Produce",
    "status": "ACTIVE",
    "is_purchased": false,
    "new_during_trip": false,
    "version": 8,
    "created_at": "2026-04-22T13:05:00Z",
    "updated_at": "2026-04-22T14:27:00Z"
  }
}
```

Response `409` returns `ConflictResponse`.

## 4. Delete Item

`DELETE /api/items/{item_id}`

Request body optional:

```json
{
  "base_version": 8
}
```

Response `204`

- no body

Response `409`

- if version supplied and stale

## 5. Toggle Purchased

`POST /api/items/{item_id}/toggle-purchased`

Request:

```json
{
  "base_version": 8,
  "is_purchased": true
}
```

Response `200`

```json
{
  "item": {
    "id": 101,
    "name": "Apples",
    "quantity": "8.000",
    "unit": null,
    "notes": "Honeycrisp if available",
    "category_id": 1,
    "category_name": "Produce",
    "status": "ACTIVE",
    "is_purchased": true,
    "new_during_trip": false,
    "version": 9,
    "created_at": "2026-04-22T13:05:00Z",
    "updated_at": "2026-04-22T14:28:00Z"
  }
}
```

Rules:

- allowed only during active trip
- when set to `true`, clear `new_during_trip`

Response `422`

```json
{
  "error": {
    "code": "trip_not_active",
    "message": "Items can only be checked off during an active shopping trip."
  }
}
```

## 6. Create Category

`POST /api/categories`

Request:

```json
{
  "name": "Bakery"
}
```

Response `201`

```json
{
  "category": {
    "id": 7,
    "name": "Bakery",
    "sort_order": 70,
    "version": 1
  }
}
```

## 7. Rename Category

`PATCH /api/categories/{category_id}`

Request:

```json
{
  "base_version": 3,
  "name": "Fresh Produce"
}
```

Response `200`

```json
{
  "category": {
    "id": 1,
    "name": "Fresh Produce",
    "sort_order": 10,
    "version": 4
  },
  "updated_item_count": 12
}
```

Rules:

- rename applies immediately to all items in the category

Response `409`

- same conflict shape as item conflict, with `entity_type: "category"`

## 8. Delete Category

`DELETE /api/categories/{category_id}`

Request:

```json
{
  "base_version": 4,
  "confirm": true
}
```

Response `204`

Response `422` if category contains items:

```json
{
  "error": {
    "code": "category_not_empty",
    "message": "Move all items out of this category before deleting it."
  }
}
```

Rules:

- delete only allowed when empty
- confirmation required

## 9. Start Trip

`POST /api/trips/start`

Request:

```json
{}
```

Response `201`

```json
{
  "trip": {
    "id": 4,
    "status": "ACTIVE",
    "started_at": "2026-04-22T14:30:00Z",
    "completed_at": null,
    "version": 1
  }
}
```

Response `422`

```json
{
  "error": {
    "code": "empty_list",
    "message": "A shopping trip can only be started when the list has at least one item."
  }
}
```

Response `409`

```json
{
  "error": {
    "code": "trip_already_active",
    "message": "A shopping trip is already in progress."
  }
}
```

## 10. Prepare Finish Trip

`POST /api/trips/{trip_id}/finish/prepare`

Purpose:

- gather unchecked items for item-by-item carryover review

Request:

```json
{
  "base_version": 1
}
```

Response `200`

```json
{
  "trip": {
    "id": 4,
    "status": "ACTIVE",
    "started_at": "2026-04-22T14:30:00Z",
    "completed_at": null,
    "version": 1
  },
  "unchecked_items": [
    {
      "id": 201,
      "name": "Bread",
      "quantity": "1.000",
      "unit": null,
      "notes": "",
      "category_id": 7,
      "category_name": "Bakery",
      "status": "ACTIVE",
      "is_purchased": false,
      "new_during_trip": false,
      "version": 2,
      "created_at": "2026-04-22T14:00:00Z",
      "updated_at": "2026-04-22T14:10:00Z"
    }
  ]
}
```

## 11. Complete Finish Trip

`POST /api/trips/{trip_id}/finish/complete`

Request:

```json
{
  "base_version": 1,
  "carryover_items": [
    {
      "item_id": 201,
      "carry_over": true
    },
    {
      "item_id": 202,
      "carry_over": false
    }
  ]
}
```

Response `200`

```json
{
  "archived_list": {
    "id": 12,
    "status": "ARCHIVED",
    "archived_at": "2026-04-22T14:40:00Z"
  },
  "new_active_list": {
    "id": 13,
    "status": "ACTIVE",
    "version": 1,
    "created_at": "2026-04-22T14:40:00Z"
  },
  "carried_over_items": [
    {
      "id": 301,
      "name": "Bread",
      "quantity": "1.000",
      "unit": null,
      "notes": "",
      "category_id": 7,
      "category_name": "Bakery",
      "status": "ACTIVE",
      "is_purchased": false,
      "new_during_trip": false,
      "version": 1,
      "created_at": "2026-04-22T14:40:00Z",
      "updated_at": "2026-04-22T14:40:00Z"
    }
  ],
  "trip": {
    "id": 4,
    "status": "COMPLETED",
    "started_at": "2026-04-22T14:30:00Z",
    "completed_at": "2026-04-22T14:40:00Z",
    "version": 2
  }
}
```

## 12. Resolve Duplicate

`POST /api/duplicates/{pending_confirmation_id}/resolve`

Request for merge:

```json
{
  "decision": "merge"
}
```

Request for keep separate:

```json
{
  "decision": "keep_separate"
}
```

Request for cancel:

```json
{
  "decision": "cancel"
}
```

Response `200`

```json
{
  "decision": "merge",
  "resolved_item": {
    "id": 88,
    "name": "Milk",
    "quantity": "2.000",
    "unit": "gal",
    "notes": "",
    "category_id": 99,
    "category_name": "Dairy",
    "status": "ACTIVE",
    "is_purchased": false,
    "new_during_trip": false,
    "version": 4,
    "created_at": "2026-04-22T13:10:00Z",
    "updated_at": "2026-04-22T14:31:00Z"
  },
  "removed_pending_item_id": 146
}
```

For `keep_separate`:

```json
{
  "decision": "keep_separate",
  "resolved_item": {
    "id": 146,
    "name": "Milk",
    "quantity": "1.000",
    "unit": null,
    "notes": "2%",
    "category_id": 99,
    "category_name": "Dairy",
    "status": "ACTIVE",
    "is_purchased": false,
    "new_during_trip": true,
    "version": 2,
    "created_at": "2026-04-22T14:25:00Z",
    "updated_at": "2026-04-22T14:31:00Z"
  }
}
```

For `cancel`:

```json
{
  "decision": "cancel",
  "removed_pending_item_id": 146
}
```

## 13. Resolve Conflict

`POST /api/conflicts/resolve`

Purpose:

- user chooses which whole-record version to keep

Request choosing server version:

```json
{
  "entity_type": "item",
  "entity_id": 101,
  "decision": "keep_server",
  "server_version": 8
}
```

Request choosing client version:

```json
{
  "entity_type": "item",
  "entity_id": 101,
  "decision": "overwrite_with_client",
  "server_version": 8,
  "client_payload": {
    "name": "Green onions",
    "quantity": "2.000",
    "notes": ""
  }
}
```

Response `200`

```json
{
  "entity_type": "item",
  "entity_id": 101,
  "decision": "overwrite_with_client",
  "item": {
    "id": 101,
    "name": "Green onions",
    "quantity": "2.000",
    "unit": null,
    "notes": "",
    "category_id": 1,
    "category_name": "Produce",
    "status": "ACTIVE",
    "is_purchased": false,
    "new_during_trip": false,
    "version": 9,
    "created_at": "2026-04-22T13:05:00Z",
    "updated_at": "2026-04-22T14:32:00Z"
  }
}
```

## 14. Realtime Stream

`GET /api/events/stream`

Headers:

- `X-App-Token: <token>`
- optional `Last-Event-ID: 502`

Response:

- `text/event-stream`

Event format:

```text
id: 503
event: item.updated
data: {"item":{"id":101,"name":"Apples","quantity":"8.000","category_id":1,"category_name":"Produce","is_purchased":true,"new_during_trip":false,"version":9,"updated_at":"2026-04-22T14:28:00Z"}}
```

Suggested event types:

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

`snapshot.required` event:

```text
id: 550
event: snapshot.required
data: {"reason":"replay_gap"}
```

## 15. Health of Shared Link

Optional but useful:

`GET /api/meta`

Response `200`

```json
{
  "app_name": "Shopping Agent",
  "mode": "shared_link",
  "realtime": "sse"
}
```

## Validation Rules

- `name`: required for item create, non-empty after trim
- `quantity`: nullable, decimal string if present
- `category name`: non-empty, case-insensitive uniqueness
- `base_version`: required on all mutating update endpoints except create
- `confirm=true`: required for category delete
- purchased toggle only valid during active trip
- trip start requires at least one active non-pending item

## Recommended Status Code Summary

- `200`: success
- `201`: created
- `202`: accepted/pending duplicate review
- `204`: successful delete with no body
- `403`: invalid shared token
- `404`: entity not found
- `409`: optimistic concurrency conflict
- `422`: validation/business rule violation

## Recommended Backend Response Normalization

To keep the frontend simple, every returned item should always include:

- `id`
- `name`
- `quantity`
- `unit`
- `notes`
- `category_id`
- `category_name`
- `status`
- `is_purchased`
- `new_during_trip`
- `version`
- `created_at`
- `updated_at`

Every category should always include:

- `id`
- `name`
- `sort_order`
- `version`
