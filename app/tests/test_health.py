"""
Tests for the health endpoint.
"""
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_returns_200(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok_json(self, client: TestClient):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    def test_health_content_type_json(self, client: TestClient):
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]
