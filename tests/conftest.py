"""pytest fixtures for backend unit tests."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import AsyncIterator, Dict, Any, List

import pytest
from pydantic import BaseModel
import respx
import httpx
from fastapi.testclient import TestClient

# Set environment variables before importing app module.
os.environ.setdefault("REDMINE_BASE_URL", "http://test-redmine:3000")
os.environ.setdefault("REDMINE_API_KEY", "test_api_key_12345")
os.environ.setdefault("REDMINE_PROJECT_ID", "99")

# Import after env vars are set.
from src.backend.app import app, get_session_store, _status_by_id, _status_by_key, _status_by_name
from src.backend.auth import SessionData


class FakeSessionStore:
    def __init__(self):
        self.sessions = {
            "test-session": SessionData(
                redmine_user_id=7,
                username="test-user",
                name="Test User",
                redmine_api_key="user_specific_api_key",
                created_at="2026-01-01T00:00:00+00:00",
            )
        }
        self.deleted = []

    async def create(self, data):
        self.sessions["new-session"] = data
        return "new-session"

    async def get(self, session_id):
        return self.sessions.get(session_id)

    async def delete(self, session_id):
        self.deleted.append(session_id)
        self.sessions.pop(session_id, None)


# ── Mock Redmine API responses ────────────────────────────────────

MOCK_STATUSES: List[Dict[str, Any]] = [
    {"id": 1, "name": "新規", "slug": "new"},
    {"id": 2, "name": "対応中", "slug": "in_progress"},
    {"id": 3, "name": "回答済", "slug": "resolved"},
    {"id": 4, "name": "追加質問", "slug": "feedback"},
    {"id": 5, "name": "クローズ", "slug": "closed"},
    {"id": 6, "name": "クローズ待ち", "slug": "rejected"},
]

MOCK_TRACKERS: List[Dict[str, Any]] = [
    {"id": 1, "name": "Bug"},
    {"id": 2, "name": "Feature"},
    {"id": 3, "name": "問い合わせ"},
]

MOCK_TICKET_CREATED: Dict[str, Any] = {
    "issue": {
        "id": 100,
        "subject": "テスト件名",
        "description": "テスト本文",
        "status": {"id": 1, "name": "新規"},
        "priority": {"id": 3, "name": "Normal"},
        "created_on": "2024-01-01T00:00:00Z",
        "updated_on": "2024-01-01T00:00:00Z",
    }
}

MOCK_TICKET_DETAIL: Dict[str, Any] = {
    "issue": {
        "id": 100,
        "subject": "テスト件名",
        "description": "テスト本文",
        "status": {"id": 2, "name": "対応中"},
        "priority": {"id": 3, "name": "Normal"},
        "author": {"id": 8, "name": "Sales User"},
        "assigned_to": {"id": 7, "name": "Test User"},
        "created_on": "2024-01-01T00:00:00Z",
        "updated_on": "2024-01-02T10:00:00Z",
        "journals": [
            {
                "id": 1,
                "notes": "初期コメントです",
                "user": {"name": "admin"},
                "created_on": "2024-01-01T00:05:00Z",
                "details": [
                    {
                        "prop_key": "status_id",
                        "old_value": "新規",
                        "new_value": "対応中",
                    }
                ],
            },
            {
                "id": 2,
                "notes": "追加の質問です",
                "user": {"name": "sales_user"},
                "created_on": "2024-01-02T10:00:00Z",
                "details": [
                    {
                        "prop_key": "assigned_to_id",
                        "old_value": None,
                        "new_value": "7",
                    }
                ],
            },
        ],
    }
}

MOCK_TICKET_LIST: Dict[str, Any] = {
    "issues": [
        {
            "id": 100,
            "subject": "チケットA",
            "description": "説明A",
            "author": {"id": 8, "name": "Sales User"},
            "status": {"id": 1, "name": "新規"},
            "priority": {"id": 2, "name": "High"},
            "created_on": "2024-01-01T00:00:00Z",
            "updated_on": "2024-01-01T00:00:00Z",
        },
        {
            "id": 101,
            "subject": "チケットB",
            "description": "説明B",
            "author": {"id": 7, "name": "Test User"},
            "status": {"id": 2, "name": "対応中"},
            "priority": {"id": 3, "name": "Normal"},
            "assigned_to": {"id": 7, "name": "Test User"},
            "created_on": "2024-01-02T00:00:00Z",
            "updated_on": "2024-01-02T00:00:00Z",
        },
    ],
    "total_count": 2,
}


@pytest.fixture
def mock_redmine_api():
    """Mock all Redmine REST API endpoints with respx."""
    with respx.mock:
        current_ticket_detail = deepcopy(MOCK_TICKET_DETAIL)
        # Mock /issue_statuses.json
        respx.get("http://test-redmine:3000/issue_statuses.json").mock(
            return_value=httpx.Response(200, json={"issue_statuses": MOCK_STATUSES})
        )

        # Mock /trackers.json
        respx.get("http://test-redmine:3000/trackers.json").mock(
            return_value=httpx.Response(200, json={"trackers": MOCK_TRACKERS})
        )

        respx.get(
            "http://test-redmine:3000/projects/99/memberships.json"
        ).mock(
            return_value=httpx.Response(
                200,
                json={
                    "memberships": [
                        {
                            "user": {"id": 7, "name": "Test User"},
                            "roles": [{"id": 2, "name": "サポート担当者"}],
                        },
                        {
                            "user": {"id": 8, "name": "Sales User"},
                            "roles": [{"id": 3, "name": "営業担当者"}],
                        },
                    ],
                    "total_count": 2,
                },
            )
        )

        # Mock POST /issues.json (create ticket)
        respx.post("http://test-redmine:3000/issues.json").mock(
            return_value=httpx.Response(201, json=MOCK_TICKET_CREATED)
        )

        # Mock GET /issues.json (list tickets)
        def list_handler(request: httpx.Request):
            params = request.url.params
            status_id = params.get("status_id")
            if status_id == "open":  # Responder view: all non-closed tickets
                sales_assigned = {
                    **MOCK_TICKET_LIST["issues"][0],
                    "id": 102,
                    "subject": "営業担当者へ割り当て済み",
                    "assigned_to": {"id": 8, "name": "Sales User"},
                }
                return httpx.Response(
                    200,
                    json={
                        "issues": [*MOCK_TICKET_LIST["issues"], sales_assigned],
                        "total_count": 3,
                    },
                )
            elif status_id == "1":  # Filter by New status
                return httpx.Response(200, json={
                    "issues": [MOCK_TICKET_LIST["issues"][0]],
                    "total_count": 1,
                })
            elif status_id == "2":  # Filter by In Progress status
                return httpx.Response(200, json={
                    "issues": [MOCK_TICKET_LIST["issues"][1]],
                    "total_count": 1,
                })
            return httpx.Response(200, json=MOCK_TICKET_LIST)

        respx.get("http://test-redmine:3000/issues.json").mock(side_effect=list_handler)

        # Mock GET /issues/{id}.json (ticket detail)
        respx.get(url__regex=r"http://test-redmine:3000/issues/\d+\.json").mock(
            side_effect=lambda request: httpx.Response(
                200, json=current_ticket_detail
            )
        )

        # Mock PUT /issues/{id}.json (update ticket - for comments and status changes)
        def update_handler(request: httpx.Request):
            payload = json.loads(request.content).get("issue", {})
            if "status_id" in payload:
                status_id = int(payload["status_id"])
                status = next(s for s in MOCK_STATUSES if s["id"] == status_id)
                current_ticket_detail["issue"]["status"] = {
                    "id": status["id"],
                    "name": status["name"],
                }
            if "assigned_to_id" in payload:
                assigned_to_id = payload["assigned_to_id"]
                current_ticket_detail["issue"]["assigned_to"] = (
                    {"id": assigned_to_id, "name": "Test User"}
                    if assigned_to_id not in (None, "")
                    else None
                )
            return httpx.Response(
                200, json={"issue": current_ticket_detail["issue"]}
            )

        respx.put(url__regex=r"http://test-redmine:3000/issues/\d+\.json").mock(
            side_effect=update_handler
        )

        yield


@pytest.fixture
def client(mock_redmine_api) -> TestClient:
    """FastAPI test client with mocked Redmine API."""
    # Reset status caches before each test.
    _status_by_id.clear()
    _status_by_key.clear()
    _status_by_name.clear()

    store = FakeSessionStore()
    app.dependency_overrides[get_session_store] = lambda: store
    with TestClient(app, cookies={"session_id": "test-session"}) as c:
        yield c
    app.dependency_overrides.clear()
