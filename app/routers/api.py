"""Web API router."""
import asyncio
from datetime import datetime

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Category, Item, ShoppingList, ShoppingTrip, User, PendingConfirmation
from app.models.shopping_list import ListStatus
from app.models.shopping_trip import TripStatus
from app.services import category_service, trip_service
from app.services import item_service
from app.services.conflict_service import (
    build_category_conflict,
    build_item_conflict,
    resolve_category_conflict,
    resolve_item_conflict,
)
from app.services.duplicate_service import check_duplicates
from app.services.duplicate_resolution_service import resolve_duplicate
from app.services.realtime_service import list_events_after

router = APIRouter(prefix="/api", tags=["api"])


def _require_app_token(x_app_token: str = Header(default="")) -> None:
    if x_app_token != settings.web_shared_token:
        raise HTTPException(status_code=403, detail="Invalid app token")


def _require_stream_token(token: str = Query(default="")) -> None:
    if token != settings.web_shared_token:
        raise HTTPException(status_code=403, detail="Invalid app token")


def _get_or_create_active_list(db: Session) -> ShoppingList:
    active_list = (
        db.query(ShoppingList)
        .filter(ShoppingList.status == ListStatus.ACTIVE)
        .first()
    )
    if active_list is None:
        active_list = ShoppingList(status=ListStatus.ACTIVE)
        db.add(active_list)
        db.commit()
        db.refresh(active_list)
    return active_list


def _serialize_trip(trip: ShoppingTrip | None) -> dict | None:
    if trip is None:
        return None
    return {
        "id": trip.id,
        "status": trip.status.value,
        "started_at": trip.started_at.isoformat().replace("+00:00", "Z") if trip.started_at else None,
        "completed_at": trip.completed_at.isoformat().replace("+00:00", "Z") if trip.completed_at else None,
        "version": trip.version,
    }


def _serialize_item(item: Item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "quantity": str(item.quantity) if item.quantity is not None else None,
        "unit": item.unit,
        "notes": item.notes,
        "category_id": item.category_id,
        "category_name": item.category or "Uncategorized",
        "status": item.status.value,
        "is_purchased": item.is_purchased,
        "new_during_trip": item.new_during_trip,
        "version": item.version,
        "created_at": item.created_at.isoformat().replace("+00:00", "Z") if item.created_at else None,
        "updated_at": item.updated_at.isoformat().replace("+00:00", "Z") if item.updated_at else None,
    }


def _error_response(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def _serialize_sse_event(event) -> str:
    return f"id: {event.id}\nevent: {event.event_type}\ndata: {event.payload_json}\n\n"


@router.get("/app-state", dependencies=[Depends(_require_app_token)])
def get_app_state(db: Session = Depends(get_db)) -> dict:
    active_list = _get_or_create_active_list(db)
    trip = (
        db.query(ShoppingTrip)
        .filter(
            ShoppingTrip.list_id == active_list.id,
            ShoppingTrip.status == TripStatus.ACTIVE,
        )
        .first()
    )

    categories = db.query(Category).order_by(Category.sort_order, Category.id).all()
    items = (
        db.query(Item)
        .filter(Item.list_id == active_list.id)
        .order_by(Item.category, Item.name, Item.id)
        .all()
    )

    grouped: list[dict] = []
    for category in categories:
        category_items = [item for item in items if item.category_id == category.id]
        if not category_items:
            continue
        grouped.append(
            {
                "category": {
                    "id": category.id,
                    "name": category.name,
                    "sort_order": category.sort_order,
                    "version": category.version,
                },
                "items": [_serialize_item(item) for item in category_items],
            }
        )

    uncategorized_items = [item for item in items if item.category_id is None]
    if uncategorized_items:
        grouped.append(
            {
                "category": {
                    "id": None,
                    "name": "Uncategorized",
                    "sort_order": 999999,
                    "version": 1,
                },
                "items": [_serialize_item(item) for item in uncategorized_items],
            }
        )

    return {
        "list": {
            "id": active_list.id,
            "status": active_list.status.value,
            "version": active_list.version,
            "created_at": active_list.created_at.isoformat().replace("+00:00", "Z") if active_list.created_at else None,
        },
        "trip": _serialize_trip(trip),
        "categories": [
            {
                "id": category.id,
                "name": category.name,
                "sort_order": category.sort_order,
                "version": category.version,
            }
            for category in categories
        ],
        "items_by_category": grouped,
        "pending_prompts": {
            "duplicate": None,
            "conflict": None,
            "trip_finish": None,
        },
        "server_time": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/events/stream", dependencies=[Depends(_require_stream_token)])
async def stream_events(
    request: Request,
    last_event_id: int = Query(default=0),
    last_event_id_header: str | None = Header(default=None, alias="Last-Event-ID"),
    stream_once: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    async def event_generator():
        current_event_id = last_event_id or int(last_event_id_header or 0)
        while True:
            events = list_events_after(current_event_id, db)
            for event in events:
                current_event_id = event.id
                yield _serialize_sse_event(event)
            if stream_once:
                break
            if await request.is_disconnected():
                break
            await asyncio.sleep(0.25)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/items", dependencies=[Depends(_require_app_token)], status_code=201)
def create_item(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    item_payload = {
        "name": payload["name"],
        "quantity": payload.get("quantity"),
        "unit": payload.get("unit"),
        "notes": payload.get("notes"),
        "category": payload.get("category"),
        "category_id": payload.get("category_id"),
    }
    duplicate_result = check_duplicates([item_payload], db)
    if duplicate_result["possible_duplicates"]:
        first_user = db.query(User).order_by(User.id).first()
        new_item, existing_item, _score = duplicate_result["possible_duplicates"][0]
        pending_item = item_service.hold_pending(
            item_dict=new_item,
            existing_item_id=existing_item.id,
            triggered_by=first_user.id if first_user else 1,
            db=db,
        )
        confirmation = (
            db.query(PendingConfirmation)
            .filter(PendingConfirmation.item_id == pending_item.id)
            .order_by(PendingConfirmation.id.desc())
            .first()
        )
        return JSONResponse(
            status_code=202,
            content={
                "pending_duplicate": {
                    "pending_confirmation_id": confirmation.id,
                    "pending_item": _serialize_item(pending_item),
                    "existing_item": _serialize_item(existing_item),
                    "options": ["merge", "keep_separate", "cancel"],
                },
                "client_request_id": payload.get("client_request_id"),
            },
        )

    created = item_service.add_items([item_payload], list_id=None, user_id=None, db=db)
    item = created[0]
    return {
        "item": _serialize_item(item),
        "client_request_id": payload.get("client_request_id"),
        "duplicate_check": {"status": "clear"},
    }


@router.patch("/items/{item_id}", dependencies=[Depends(_require_app_token)])
def update_item(item_id: int, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    existing = db.query(Item).filter(Item.id == item_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if payload.get("base_version") != existing.version:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "version_conflict",
                    "message": "This item was updated before your changes were saved.",
                },
                "conflict": build_item_conflict(existing, {key: value for key, value in payload.items() if key != "base_version"}),
            },
        )
    updates = {key: value for key, value in payload.items() if key != "base_version"}
    item = item_service.update_item(item_id, updates, db=db)
    return {"item": _serialize_item(item)}


@router.delete("/items/{item_id}", dependencies=[Depends(_require_app_token)], status_code=204)
def delete_item(item_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> Response:
    item_service.delete_item(item_id, db=db)
    return Response(status_code=204)


@router.post("/items/{item_id}/toggle-purchased", dependencies=[Depends(_require_app_token)])
def toggle_item_purchased(item_id: int, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    try:
        item = item_service.toggle_purchased(item_id, bool(payload["is_purchased"]), db=db)
    except ValueError as exc:
        if "active shopping trip" in str(exc):
            return JSONResponse(
                status_code=422,
                content=_error_response("trip_not_active", str(exc)),
            )
        raise
    return {"item": _serialize_item(item)}


@router.post("/categories", dependencies=[Depends(_require_app_token)], status_code=201)
def create_category(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    category = category_service.create_category(payload["name"], db)
    return {
        "category": {
            "id": category.id,
            "name": category.name,
            "sort_order": category.sort_order,
            "version": category.version,
        }
    }


@router.patch("/categories/{category_id}", dependencies=[Depends(_require_app_token)])
def rename_category(category_id: int, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    existing = db.query(Category).filter(Category.id == category_id).first()
    if existing is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if payload.get("base_version") != existing.version:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "version_conflict",
                    "message": "This category was updated before your changes were saved.",
                },
                "conflict": build_category_conflict(existing, {key: value for key, value in payload.items() if key != "base_version"}),
            },
        )
    category = category_service.rename_category(category_id, payload["name"], db)
    updated_item_count = db.query(Item).filter(Item.category_id == category.id).count()
    return {
        "category": {
            "id": category.id,
            "name": category.name,
            "sort_order": category.sort_order,
            "version": category.version,
        },
        "updated_item_count": updated_item_count,
    }


@router.delete("/categories/{category_id}", dependencies=[Depends(_require_app_token)], status_code=204)
def delete_category(category_id: int, payload: dict = Body(default={}), db: Session = Depends(get_db)) -> Response:
    try:
        category_service.delete_category(category_id, db)
    except ValueError as exc:
        if "Move all items out of this category" in str(exc):
            return JSONResponse(
                status_code=422,
                content=_error_response("category_not_empty", str(exc)),
            )
        raise
    return Response(status_code=204)


@router.post("/trips/start", dependencies=[Depends(_require_app_token)], status_code=201)
def start_trip(payload: dict = Body(default={}), db: Session = Depends(get_db)) -> dict:
    try:
        trip = trip_service.start_trip(db)
    except ValueError as exc:
        message = str(exc)
        if "at least one item" in message:
            return JSONResponse(status_code=422, content=_error_response("empty_list", message))
        raise
    return {"trip": _serialize_trip(trip)}


@router.post("/trips/{trip_id}/finish/prepare", dependencies=[Depends(_require_app_token)])
def prepare_finish_trip(trip_id: int, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    trip, unchecked_items = trip_service.prepare_finish_trip(trip_id, db)
    return {
        "trip": _serialize_trip(trip),
        "unchecked_items": [_serialize_item(item) for item in unchecked_items],
    }


@router.post("/trips/{trip_id}/finish/complete", dependencies=[Depends(_require_app_token)])
def complete_finish_trip(trip_id: int, payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    trip, archived_list, new_list, carried_items = trip_service.complete_finish_trip(
        trip_id,
        payload.get("carryover_items", []),
        db,
    )
    return {
        "archived_list": {
            "id": archived_list.id,
            "status": archived_list.status.value,
            "archived_at": archived_list.archived_at.isoformat().replace("+00:00", "Z") if archived_list.archived_at else None,
        },
        "new_active_list": {
            "id": new_list.id,
            "status": new_list.status.value,
            "version": new_list.version,
            "created_at": new_list.created_at.isoformat().replace("+00:00", "Z") if new_list.created_at else None,
        },
        "carried_over_items": [_serialize_item(item) for item in carried_items],
        "trip": _serialize_trip(trip),
    }


@router.post("/duplicates/{pending_confirmation_id}/resolve", dependencies=[Depends(_require_app_token)])
def resolve_duplicate_endpoint(
    pending_confirmation_id: int,
    payload: dict = Body(...),
    db: Session = Depends(get_db),
) -> dict:
    result = resolve_duplicate(
        pending_confirmation_id=pending_confirmation_id,
        decision=payload["decision"],
        db=db,
    )
    if "resolved_item" in result:
        return {
            "decision": result["decision"],
            "resolved_item": _serialize_item(result["resolved_item"]),
        }
    return result


@router.post("/conflicts/resolve", dependencies=[Depends(_require_app_token)])
def resolve_conflict(payload: dict = Body(...), db: Session = Depends(get_db)) -> dict:
    if payload["entity_type"] == "item":
        item = resolve_item_conflict(
            item_id=payload["entity_id"],
            decision=payload["decision"],
            server_version=payload["server_version"],
            client_payload=payload.get("client_payload", {}),
            db=db,
        )
        return {
            "entity_type": "item",
            "entity_id": item.id,
            "decision": payload["decision"],
            "item": _serialize_item(item),
        }
    if payload["entity_type"] == "category":
        category = resolve_category_conflict(
            category_id=payload["entity_id"],
            decision=payload["decision"],
            server_version=payload["server_version"],
            client_payload=payload.get("client_payload", {}),
            db=db,
        )
        return {
            "entity_type": "category",
            "entity_id": category.id,
            "decision": payload["decision"],
            "category": {
                "id": category.id,
                "name": category.name,
                "sort_order": category.sort_order,
                "version": category.version,
            },
        }

    raise HTTPException(status_code=422, detail="Unsupported entity type")
