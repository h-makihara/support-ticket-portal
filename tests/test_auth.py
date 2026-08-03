"""Authentication and session API tests."""

import httpx
import respx
from fastapi.testclient import TestClient

from src.backend.app import app, get_session_store
from tests.conftest import FakeSessionStore


def test_session_requires_cookie(client: TestClient):
    client.cookies.clear()
    response = client.get("/auth/session")
    assert response.status_code == 401


def test_health_response_does_not_expose_configuration(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_current_session_does_not_expose_api_key(client: TestClient):
    response = client.get("/auth/session")
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "test-user"
    assert response.json()["user"]["is_support"] is True
    assert response.json()["user"]["is_sales"] is False
    assert "api_key" not in response.text


def test_logout_deletes_session(client: TestClient):
    store = app.dependency_overrides[get_session_store]()
    response = client.post("/auth/logout")
    assert response.status_code == 200
    assert "test-session" in store.deleted


def test_login_delegates_to_redmine_and_sets_httponly_cookie(mock_redmine_api):
    store = FakeSessionStore()
    app.dependency_overrides[get_session_store] = lambda: store
    route = respx.get("http://test-redmine:3000/users/current.json").mock(
        return_value=httpx.Response(200, json={"user": {
            "id": 42, "login": "alice", "firstname": "Alice",
            "lastname": "Example", "api_key": "alice-secret-key"
        }})
    )
    with TestClient(app) as test_client:
        response = test_client.post(
            "/auth/login", json={"username": "alice", "password": "secret"}
        )
    assert route.called
    assert response.status_code == 200
    assert "alice-secret-key" not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert store.sessions["new-session"].redmine_api_key == "alice-secret-key"
    app.dependency_overrides.clear()


def test_login_rejects_invalid_credentials(mock_redmine_api):
    store = FakeSessionStore()
    app.dependency_overrides[get_session_store] = lambda: store
    respx.get("http://test-redmine:3000/users/current.json").mock(
        return_value=httpx.Response(401)
    )
    with TestClient(app) as test_client:
        response = test_client.post(
            "/auth/login", json={"username": "unknown", "password": "wrong"}
        )
    assert response.status_code == 401
    assert "new-session" not in store.sessions
    app.dependency_overrides.clear()
