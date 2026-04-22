"""Tests for web API endpoints."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Category, Item, ListEvent, PendingConfirmation, ShoppingList, ShoppingTrip
from app.models.item import ItemStatus
from app.models.shopping_list import ListStatus
from app.models.shopping_trip import TripStatus


@pytest.fixture
def api_client(db: Session):
    from app.routers.api import router as api_router

    test_app = FastAPI(title="Shopping Agent API Test")
    test_app.include_router(api_router)

    def override_get_db():
        yield db

    test_app.dependency_overrides[get_db] = override_get_db

    with TestClient(test_app, raise_server_exceptions=True) as client:
        yield client


def _auth_headers() -> dict[str, str]:
    return {"X-App-Token": settings.web_shared_token}


class TestAppStateAuth:
    def test_rejects_missing_token(self, api_client: TestClient):
        response = api_client.get("/api/app-state")
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid app token"

    def test_rejects_invalid_token(self, api_client: TestClient):
        response = api_client.get("/api/app-state", headers={"X-App-Token": "wrong"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid app token"


class TestAppState:
    def test_returns_empty_snapshot_and_creates_active_list(self, api_client: TestClient, db: Session):
        response = api_client.get("/api/app-state", headers=_auth_headers())

        assert response.status_code == 200
        payload = response.json()

        assert payload["list"]["status"] == "ACTIVE"
        assert payload["trip"] is None
        assert payload["categories"] == []
        assert payload["items_by_category"] == []
        assert payload["pending_prompts"] == {
            "duplicate": None,
            "conflict": None,
            "trip_finish": None,
        }

        active_lists = db.query(ShoppingList).filter(ShoppingList.status == ListStatus.ACTIVE).all()
        assert len(active_lists) == 1

    def test_returns_current_trip_categories_and_grouped_items(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()

        produce = Category(name="Produce", normalized_name="produce", sort_order=20)
        dairy = Category(name="Dairy", normalized_name="dairy", sort_order=10)
        db.add_all([produce, dairy])
        db.flush()

        db.add_all(
            [
                Item(list_id=sl.id, name="Milk", category="Dairy", category_id=dairy.id, quantity=1),
                Item(list_id=sl.id, name="Apples", category="Produce", category_id=produce.id, quantity=6),
            ]
        )
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE)
        db.add(trip)
        db.commit()

        response = api_client.get("/api/app-state", headers=_auth_headers())

        assert response.status_code == 200
        payload = response.json()

        assert payload["list"]["id"] == sl.id
        assert payload["trip"]["id"] == trip.id
        assert payload["trip"]["status"] == "ACTIVE"
        assert [category["name"] for category in payload["categories"]] == ["Dairy", "Produce"]

        grouped = payload["items_by_category"]
        assert [group["category"]["name"] for group in grouped] == ["Dairy", "Produce"]
        assert grouped[0]["items"][0]["name"] == "Milk"
        assert grouped[1]["items"][0]["name"] == "Apples"


class TestItemEndpoints:
    def test_create_item(self, api_client: TestClient, db: Session):
        response = api_client.post(
            "/api/items",
            headers=_auth_headers(),
            json={
                "name": "Milk",
                "quantity": 1,
                "notes": "2%",
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["item"]["name"] == "Milk"
        assert payload["item"]["notes"] == "2%"
        assert payload["duplicate_check"]["status"] == "clear"

        item = db.query(Item).filter(Item.name == "Milk").first()
        assert item is not None

    def test_create_item_defaults_quantity_and_marks_new_during_trip(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        response = api_client.post(
            "/api/items",
            headers=_auth_headers(),
            json={"name": "Milk"},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["item"]["quantity"] == "1.000"
        assert payload["item"]["new_during_trip"] is True

    def test_create_item_returns_pending_duplicate_payload(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        existing = Item(list_id=sl.id, name="Milk", status=ItemStatus.ACTIVE, quantity=1)
        db.add(existing)
        db.commit()

        response = api_client.post(
            "/api/items",
            headers=_auth_headers(),
            json={"name": "Milk", "notes": "2%"},
        )

        assert response.status_code == 202
        payload = response.json()
        assert payload["pending_duplicate"]["existing_item"]["id"] == existing.id
        assert payload["pending_duplicate"]["pending_item"]["status"] == "PENDING"
        assert payload["pending_duplicate"]["options"] == ["merge", "keep_separate", "cancel"]

        pending_item = db.query(Item).filter(Item.status == ItemStatus.PENDING).first()
        assert pending_item is not None
        assert db.query(PendingConfirmation).filter(PendingConfirmation.item_id == pending_item.id).count() == 1

    def test_update_item(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        item = Item(list_id=sl.id, name="Apple", version=1)
        db.add(item)
        db.commit()

        response = api_client.patch(
            f"/api/items/{item.id}",
            headers=_auth_headers(),
            json={"base_version": 1, "name": "Apples", "notes": "Honeycrisp"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["item"]["name"] == "Apples"
        assert payload["item"]["notes"] == "Honeycrisp"
        assert payload["item"]["version"] == 2

    def test_update_item_returns_409_for_stale_version(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        item = Item(list_id=sl.id, name="Apple", version=2)
        db.add(item)
        db.commit()

        response = api_client.patch(
            f"/api/items/{item.id}",
            headers=_auth_headers(),
            json={"base_version": 1, "name": "Apples"},
        )

        assert response.status_code == 409
        payload = response.json()
        assert payload["error"]["code"] == "version_conflict"
        assert payload["conflict"]["entity_type"] == "item"
        assert payload["conflict"]["entity_id"] == item.id

    def test_delete_item(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        item = Item(list_id=sl.id, name="Milk")
        db.add(item)
        db.commit()

        response = api_client.request(
            "DELETE",
            f"/api/items/{item.id}",
            headers=_auth_headers(),
            json={"base_version": 1},
        )

        assert response.status_code == 204
        assert db.query(Item).filter(Item.id == item.id).first() is None

    def test_toggle_purchased(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        item = Item(list_id=sl.id, name="Milk")
        db.add(item)
        db.flush()
        db.add(ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE))
        db.commit()

        response = api_client.post(
            f"/api/items/{item.id}/toggle-purchased",
            headers=_auth_headers(),
            json={"base_version": 1, "is_purchased": True},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["item"]["is_purchased"] is True
        assert payload["item"]["version"] == 2

    def test_toggle_purchased_returns_422_without_active_trip(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        item = Item(list_id=sl.id, name="Milk")
        db.add(item)
        db.commit()

        response = api_client.post(
            f"/api/items/{item.id}/toggle-purchased",
            headers=_auth_headers(),
            json={"base_version": 1, "is_purchased": True},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "trip_not_active"


class TestCategoryEndpoints:
    def test_create_category(self, api_client: TestClient, db: Session):
        response = api_client.post(
            "/api/categories",
            headers=_auth_headers(),
            json={"name": "Produce"},
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["category"]["name"] == "Produce"

        category = db.query(Category).filter(Category.name == "Produce").first()
        assert category is not None

    def test_rename_category(self, api_client: TestClient, db: Session):
        category = Category(name="Produce", normalized_name="produce", sort_order=10, version=1)
        db.add(category)
        db.commit()

        response = api_client.patch(
            f"/api/categories/{category.id}",
            headers=_auth_headers(),
            json={"base_version": 1, "name": "Fresh Produce"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["category"]["name"] == "Fresh Produce"
        assert payload["updated_item_count"] == 0

    def test_rename_category_returns_409_for_stale_version(self, api_client: TestClient, db: Session):
        category = Category(name="Produce", normalized_name="produce", sort_order=10, version=2)
        db.add(category)
        db.commit()

        response = api_client.patch(
            f"/api/categories/{category.id}",
            headers=_auth_headers(),
            json={"base_version": 1, "name": "Fresh Produce"},
        )

        assert response.status_code == 409
        payload = response.json()
        assert payload["error"]["code"] == "version_conflict"
        assert payload["conflict"]["entity_type"] == "category"
        assert payload["conflict"]["entity_id"] == category.id

    def test_delete_category(self, api_client: TestClient, db: Session):
        category = Category(name="Produce", normalized_name="produce", sort_order=10)
        db.add(category)
        db.commit()

        response = api_client.request(
            "DELETE",
            f"/api/categories/{category.id}",
            headers=_auth_headers(),
            json={"base_version": 1, "confirm": True},
        )

        assert response.status_code == 204
        assert db.query(Category).filter(Category.id == category.id).first() is None

    def test_delete_category_returns_422_when_not_empty(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        category = Category(name="Produce", normalized_name="produce", sort_order=10)
        db.add_all([sl, category])
        db.flush()
        db.add(Item(list_id=sl.id, name="Apples", category="Produce", category_id=category.id))
        db.commit()

        response = api_client.request(
            "DELETE",
            f"/api/categories/{category.id}",
            headers=_auth_headers(),
            json={"base_version": 1, "confirm": True},
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "category_not_empty"


class TestTripEndpoints:
    def test_start_trip(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        db.add(Item(list_id=sl.id, name="Milk"))
        db.commit()

        response = api_client.post("/api/trips/start", headers=_auth_headers(), json={})

        assert response.status_code == 201
        payload = response.json()
        assert payload["trip"]["status"] == "ACTIVE"

    def test_start_trip_returns_422_for_empty_list(self, api_client: TestClient, db: Session):
        db.add(ShoppingList(status=ListStatus.ACTIVE))
        db.commit()

        response = api_client.post("/api/trips/start", headers=_auth_headers(), json={})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "empty_list"

    def test_prepare_finish_trip(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        unchecked = Item(list_id=sl.id, name="Milk", is_purchased=False)
        checked = Item(list_id=sl.id, name="Bread", is_purchased=True)
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE, version=1)
        db.add_all([unchecked, checked, trip])
        db.commit()

        response = api_client.post(
            f"/api/trips/{trip.id}/finish/prepare",
            headers=_auth_headers(),
            json={"base_version": 1},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["trip"]["id"] == trip.id
        assert [item["name"] for item in payload["unchecked_items"]] == ["Milk"]

    def test_complete_finish_trip(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        unchecked = Item(list_id=sl.id, name="Milk", is_purchased=False, category="Dairy")
        trip = ShoppingTrip(list_id=sl.id, status=TripStatus.ACTIVE, version=1)
        db.add_all([unchecked, trip])
        db.commit()

        response = api_client.post(
            f"/api/trips/{trip.id}/finish/complete",
            headers=_auth_headers(),
            json={
                "base_version": 1,
                "carryover_items": [{"item_id": unchecked.id, "carry_over": True}],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["trip"]["status"] == "COMPLETED"
        assert payload["archived_list"]["status"] == "ARCHIVED"
        assert payload["new_active_list"]["status"] == "ACTIVE"
        assert [item["name"] for item in payload["carried_over_items"]] == ["Milk"]


class TestDuplicateEndpoints:
    def test_merge_duplicate_combines_into_existing_item(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        existing = Item(list_id=sl.id, name="Milk", status=ItemStatus.ACTIVE, quantity=1)
        pending = Item(list_id=sl.id, name="Milk", status=ItemStatus.PENDING, quantity=1, notes="2%")
        db.add_all([existing, pending])
        db.flush()
        confirmation = PendingConfirmation(
            item_id=pending.id,
            existing_item_id=existing.id,
            triggered_by=1,
            expires_at=pending.created_at,
        )
        db.add(confirmation)
        db.commit()

        response = api_client.post(
            f"/api/duplicates/{confirmation.id}/resolve",
            headers=_auth_headers(),
            json={"decision": "merge"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "merge"
        assert payload["resolved_item"]["id"] == existing.id
        assert payload["resolved_item"]["quantity"] == "2.000"
        assert db.query(Item).filter(Item.id == pending.id).first() is None
        assert db.query(PendingConfirmation).filter(PendingConfirmation.id == confirmation.id).first() is None

    def test_keep_separate_promotes_pending_item(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        existing = Item(list_id=sl.id, name="Milk", status=ItemStatus.ACTIVE, quantity=1)
        pending = Item(list_id=sl.id, name="Milk", status=ItemStatus.PENDING, quantity=1)
        db.add_all([existing, pending])
        db.flush()
        confirmation = PendingConfirmation(
            item_id=pending.id,
            existing_item_id=existing.id,
            triggered_by=1,
            expires_at=pending.created_at,
        )
        db.add(confirmation)
        db.commit()

        response = api_client.post(
            f"/api/duplicates/{confirmation.id}/resolve",
            headers=_auth_headers(),
            json={"decision": "keep_separate"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "keep_separate"
        assert payload["resolved_item"]["status"] == "ACTIVE"

        db.refresh(pending)
        assert pending.status == ItemStatus.ACTIVE

    def test_cancel_duplicate_removes_pending_item(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        existing = Item(list_id=sl.id, name="Milk", status=ItemStatus.ACTIVE, quantity=1)
        pending = Item(list_id=sl.id, name="Milk", status=ItemStatus.PENDING, quantity=1)
        db.add_all([existing, pending])
        db.flush()
        confirmation = PendingConfirmation(
            item_id=pending.id,
            existing_item_id=existing.id,
            triggered_by=1,
            expires_at=pending.created_at,
        )
        db.add(confirmation)
        db.commit()

        response = api_client.post(
            f"/api/duplicates/{confirmation.id}/resolve",
            headers=_auth_headers(),
            json={"decision": "cancel"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "cancel"
        assert payload["removed_pending_item_id"] == pending.id
        assert db.query(Item).filter(Item.id == pending.id).first() is None


class TestConflictEndpoints:
    def test_overwrite_with_client_resolves_category_conflict(self, api_client: TestClient, db: Session):
        category = Category(name="Produce", normalized_name="produce", sort_order=10, version=2)
        db.add(category)
        db.commit()

        response = api_client.post(
            "/api/conflicts/resolve",
            headers=_auth_headers(),
            json={
                "entity_type": "category",
                "entity_id": category.id,
                "decision": "overwrite_with_client",
                "server_version": 2,
                "client_payload": {"name": "Fresh Produce"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["entity_type"] == "category"
        assert payload["category"]["name"] == "Fresh Produce"

    def test_overwrite_with_client_resolves_item_conflict(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        item = Item(list_id=sl.id, name="Scallions", version=3)
        db.add(item)
        db.commit()

        response = api_client.post(
            "/api/conflicts/resolve",
            headers=_auth_headers(),
            json={
                "entity_type": "item",
                "entity_id": item.id,
                "decision": "overwrite_with_client",
                "server_version": 3,
                "client_payload": {"name": "Green onions", "notes": "fresh"},
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "overwrite_with_client"
        assert payload["item"]["name"] == "Green onions"
        assert payload["item"]["notes"] == "fresh"
        assert payload["item"]["version"] == 4


class TestRealtimeStream:
    def test_rejects_missing_stream_token(self, api_client: TestClient):
        response = api_client.get("/api/events/stream")

        assert response.status_code == 403
        assert response.json()["detail"] == "Invalid app token"

    def test_streams_events_after_last_event_id(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        first = ListEvent(
            list_id=sl.id,
            event_type="item.created",
            entity_type="item",
            entity_id=1,
            payload_json='{"id": 1, "name": "Milk"}',
        )
        second = ListEvent(
            list_id=sl.id,
            event_type="item.updated",
            entity_type="item",
            entity_id=1,
            payload_json='{"id": 1, "name": "Oat milk"}',
        )
        db.add_all([first, second])
        db.commit()

        with api_client.stream(
            "GET",
            "/api/events/stream",
            params={"token": settings.web_shared_token, "last_event_id": first.id, "stream_once": True},
        ) as response:
            body = next(response.iter_text())

        assert response.status_code == 200
        assert "event: item.updated" in body
        assert f"id: {second.id}" in body
        assert '"name": "Oat milk"' in body

    def test_streams_events_after_last_event_id_header(self, api_client: TestClient, db: Session):
        sl = ShoppingList(status=ListStatus.ACTIVE)
        db.add(sl)
        db.flush()
        first = ListEvent(
            list_id=sl.id,
            event_type="category.created",
            entity_type="category",
            entity_id=1,
            payload_json='{"category": {"id": 1, "name": "Dairy"}}',
        )
        second = ListEvent(
            list_id=sl.id,
            event_type="trip.started",
            entity_type="trip",
            entity_id=2,
            payload_json='{"trip": {"id": 2, "status": "ACTIVE"}}',
        )
        db.add_all([first, second])
        db.commit()

        with api_client.stream(
            "GET",
            "/api/events/stream",
            params={"token": settings.web_shared_token, "stream_once": True},
            headers={"Last-Event-ID": str(first.id)},
        ) as response:
            body = next(response.iter_text())

        assert response.status_code == 200
        assert "event: trip.started" in body
        assert f"id: {second.id}" in body
