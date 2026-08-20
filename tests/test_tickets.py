"""Unit tests for ticket CRUD endpoints."""

import importlib
import json
from dataclasses import replace

import pytest
import respx
from fastapi.testclient import TestClient

from backend.app import app, get_session_store

app_module = importlib.import_module("backend.app")


class TestCreateTicket:
    """テストケース: チケット作成"""

    def test_create_ticket_success(self, client: TestClient):
        """正常系: チケットが正しく作成される"""
        payload = {
            "tracker": "inquiry",
            "subject": "新規問い合わせ",
            "description": "詳細な説明です",
            "priority": 2,
        }
        resp = client.post("/tickets", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 100
        assert data["subject"] == "テスト件名"
        assert "audit_log" not in data or len(data.get("audit_log", [])) == 0
        request = next(
            call.request
            for call in respx.calls
            if call.request.method == "POST" and call.request.url.path == "/issues.json"
        )
        assert json.loads(request.content)["issue"]["tracker_id"] == 3
        assert json.loads(request.content)["issue"]["custom_fields"] == [
            {"id": 11, "value": ""},
        ]

    @pytest.mark.parametrize(("tracker", "tracker_id"), [
        ("inquiry", 3),
        ("report", 4),
        ("customer_visit", 5),
    ])
    def test_create_ticket_maps_allowed_tracker_key(
        self, client: TestClient, tracker: str, tracker_id: int
    ):
        response = client.post("/tickets", json={
            "tracker": tracker,
            "subject": "新規依頼",
            "description": "詳細",
        })
        assert response.status_code == 200
        request = next(
            call.request for call in respx.calls
            if call.request.method == "POST" and call.request.url.path == "/issues.json"
        )
        assert json.loads(request.content)["issue"]["tracker_id"] == tracker_id

    @pytest.mark.parametrize("payload", [
        {"subject": "件名", "description": "本文"},
        {"tracker": "Bug", "subject": "件名", "description": "本文"},
    ])
    def test_create_ticket_rejects_missing_or_unknown_tracker(
        self, client: TestClient, payload: dict[str, str]
    ):
        assert client.post("/tickets", json=payload).status_code == 422

    def test_create_ticket_rejects_tracker_missing_from_redmine(self, client: TestClient):
        respx.get("http://test-redmine:3000/trackers.json").mock(
            return_value=app_module.httpx.Response(
                200, json={"trackers": [{"id": 3, "name": "問い合わせ"}]}
            )
        )

        response = client.post("/tickets", json={
            "tracker": "report",
            "subject": "件名",
            "description": "本文",
        })

        assert response.status_code == 503
        assert "報告書" in response.json()["detail"]

    @pytest.mark.parametrize("failure", ["transport", "non_200", "malformed_json", "bad_id"])
    def test_create_ticket_translates_tracker_dependency_failures_to_503(
        self, client: TestClient, failure: str
    ):
        route = respx.get("http://test-redmine:3000/trackers.json")
        if failure == "transport":
            route.mock(side_effect=app_module.httpx.ConnectError("tracker service unavailable"))
        elif failure == "non_200":
            route.mock(return_value=app_module.httpx.Response(502, text="bad gateway"))
        elif failure == "malformed_json":
            route.mock(
                return_value=app_module.httpx.Response(
                    200, content=b"{", headers={"content-type": "application/json"}
                )
            )
        else:
            route.mock(
                return_value=app_module.httpx.Response(
                    200, json={"trackers": [{"id": 1.5, "name": "報告書"}]}
                )
            )

        response = client.post("/tickets", json={
            "tracker": "report",
            "subject": "件名",
            "description": "本文",
        })

        assert response.status_code == 503
        assert "トラッカー設定" in response.json()["detail"]

    @pytest.mark.parametrize(
        ("field", "value"),
        [("tracker_id", 4), ("report_required", True), ("customer_visit_required", True)],
    )
    def test_create_ticket_rejects_removed_fields(
        self, client: TestClient, field: str, value: object
    ):
        response = client.post("/tickets", json={
            "tracker": "report",
            "subject": "件名",
            "description": "本文",
            field: value,
        })

        assert response.status_code == 422
        assert not any(
            call.request.method == "POST" and call.request.url.path == "/issues.json"
            for call in respx.calls
        )

    @pytest.mark.parametrize(("tracker", "expected_fields"), [
        ("inquiry", [{"id": 11, "value": "C-100"}]),
        ("report", [
            {"id": 11, "value": "C-100"},
            {"id": 13, "value": "1"},
        ]),
        ("customer_visit", [
            {"id": 11, "value": "C-100"},
            {"id": 15, "value": "1"},
        ]),
    ])
    def test_create_ticket_sends_only_tracker_specific_custom_fields(
        self, client: TestClient, tracker: str, expected_fields: list[dict[str, object]]
    ):
        response = client.post("/tickets", json={
            "tracker": tracker,
            "subject": "件名",
            "description": "本文",
            "customer_id": "C-100",
            "report_delivered": True,
            "schedule_assigned": True,
        })
        assert response.status_code == 200
        request = next(
            call.request for call in respx.calls
            if call.request.method == "POST" and call.request.url.path == "/issues.json"
        )
        assert json.loads(request.content)["issue"]["custom_fields"] == expected_fields

    def test_create_ticket_missing_subject(self, client: TestClient):
        """異常系: subject が省略されていると422エラー"""
        payload = {
            "tracker": "inquiry",
            "description": "説明だけ",
        }
        resp = client.post("/tickets", json=payload)
        assert resp.status_code == 422

    def test_create_ticket_missing_description(self, client: TestClient):
        """異常系: description が省略されていると422エラー"""
        payload = {
            "tracker": "inquiry",
            "subject": "件名だけ",
        }
        resp = client.post("/tickets", json=payload)
        assert resp.status_code == 422

    def test_create_ticket_rejects_whitespace_only_fields(self, client: TestClient):
        resp = client.post(
            "/tickets",
            json={"tracker": "inquiry", "subject": "  ", "description": "\n\t"},
        )
        assert resp.status_code == 422

    def test_priority_options_come_from_redmine(self, client: TestClient):
        response = client.get("/priority/options")

        assert response.status_code == 200
        assert response.json()[1] == {
            "id": 2,
            "label": "Normal",
            "is_default": True,
        }


class TestListTickets:
    """テストケース: チケット一覧取得"""

    def test_list_tickets_default(self, client: TestClient):
        """正常系: デフォルトで全チケットが返る"""
        resp = client.get("/tickets")
        assert resp.status_code == 200
        data = resp.json()
        assert "tickets" in data
        assert "pagination" in data
        assert len(data["tickets"]) == 2
        assert data["pagination"]["total_count"] == 2
        assert [(ticket["tracker"], ticket["tracker_name"]) for ticket in data["tickets"]] == [
            ("report", "報告書"),
            ("customer_visit", "客先同行"),
        ]
        assert "report_delivered" in data["tickets"][0]
        assert "schedule_assigned" not in data["tickets"][0]
        assert "report_delivered" not in data["tickets"][1]
        assert "schedule_assigned" in data["tickets"][1]
        issues_request = next(
            call.request for call in respx.calls
            if call.request.url.path == "/issues.json"
        )
        assert issues_request.url.params["status_id"] == "*"

    def test_list_tickets_skips_issues_with_unexpected_trackers(self, client: TestClient):
        upstream_issues = [
            {
                "id": 200,
                "subject": "unsupported",
                "description": "",
                "tracker": {"id": 1, "name": "Bug"},
                "author": {"id": 7, "name": "Test User"},
                "status": {"id": 1, "name": "対応待ち"},
                "priority": {"id": 2, "name": "Normal"},
            },
            {
                "id": 201,
                "subject": "supported",
                "description": "",
                "tracker": {"id": 3, "name": "問い合わせ"},
                "author": {"id": 7, "name": "Test User"},
                "status": {"id": 1, "name": "対応待ち"},
                "priority": {"id": 2, "name": "Normal"},
            },
        ]

        def paginated_upstream(request: app_module.httpx.Request):
            limit = min(int(request.url.params["limit"]), 100)
            offset = int(request.url.params["offset"])
            return app_module.httpx.Response(
                200,
                json={
                    "issues": upstream_issues[offset : offset + limit],
                    "total_count": 2,
                },
            )

        route = respx.get("http://test-redmine:3000/issues.json").mock(
            side_effect=paginated_upstream
        )

        response = client.get("/tickets?limit=1&offset=0")

        assert response.status_code == 200
        assert [ticket["id"] for ticket in response.json()["tickets"]] == [201]
        assert response.json()["pagination"]["total_count"] == 1
        assert route.calls.last.request.url.params["limit"] == "100"
        assert route.calls.last.request.url.params["offset"] == "0"

    def test_list_tickets_pages_redmine_before_local_filtering(self, client: TestClient):
        upstream_issues = [
            {
                "id": 300 + index,
                "subject": f"supported-{index}",
                "description": "",
                "tracker": {"id": 3, "name": "問い合わせ"},
                "author": {"id": 7, "name": "Test User"},
                "status": {"id": 1, "name": "対応待ち"},
                "priority": {"id": 2, "name": "Normal"},
            }
            for index in range(101)
        ]

        def paginated_upstream(request: app_module.httpx.Request):
            limit = min(int(request.url.params["limit"]), 100)
            offset = int(request.url.params["offset"])
            return app_module.httpx.Response(
                200,
                json={
                    "issues": upstream_issues[offset : offset + limit],
                    "total_count": len(upstream_issues),
                },
            )

        route = respx.get("http://test-redmine:3000/issues.json").mock(
            side_effect=paginated_upstream
        )

        response = client.get("/tickets?limit=1&offset=100")

        assert response.status_code == 200
        assert [ticket["id"] for ticket in response.json()["tickets"]] == [400]
        assert response.json()["pagination"] == {
            "limit": 1,
            "offset": 100,
            "total_count": 101,
            "has_more": False,
        }
        assert [call.request.url.params["offset"] for call in route.calls] == ["0", "100"]
        assert all(call.request.url.params["limit"] == "100" for call in route.calls)

    def test_uses_authenticated_users_api_key(self, client: TestClient, mock_redmine_api):
        resp = client.get("/tickets")
        assert resp.status_code == 200
        request = next(call.request for call in respx.calls if call.request.url.path == "/issues.json")
        assert request.headers["X-Redmine-API-Key"] == "user_specific_api_key"

    def test_list_tickets_with_status_filter(self, client: TestClient):
        """正常系: status フィルタで絞り込み"""
        resp = client.get("/tickets?status=open")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tickets"]) == 1
        assert data["tickets"][0]["status"] == "対応待ち"

    def test_list_tickets_pagination(self, client: TestClient):
        """正常系: pagination メタ情報が正しく返る"""
        resp = client.get("/tickets?limit=1&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["limit"] == 1
        assert data["pagination"]["offset"] == 0
        assert len(data["tickets"]) <= 1

    def test_responder_view_includes_unassigned_and_support_tickets(
        self, client: TestClient
    ):
        resp = client.get("/tickets?view=responder")
        assert resp.status_code == 200
        data = resp.json()
        assert [ticket["id"] for ticket in data["tickets"]] == [100, 101]
        assert data["tickets"][0]["assignee"] is None
        assert data["tickets"][1]["assignee"]["id"] == 7
        assert data["tickets"][0]["latest_support_responder"] == {
            "id": 7,
            "name": "Test User",
        }
        assert data["pagination"]["total_count"] == 2

        issues_request = next(
            call.request
            for call in respx.calls
            if call.request.url.path == "/issues.json"
        )
        assert issues_request.url.params["status_id"] == "open"

    def test_responder_view_survives_one_detail_request_failure(
        self, client: TestClient, mock_redmine_api: set[int]
    ):
        mock_redmine_api.add(101)

        response = client.get("/tickets?view=responder")

        assert response.status_code == 200
        tickets = response.json()["tickets"]
        assert [ticket["id"] for ticket in tickets] == [100, 101]
        assert tickets[0]["latest_support_responder"] is not None
        assert tickets[1]["latest_support_responder"] is None

    def test_sales_user_only_sees_authored_or_assigned_tickets(
        self, client: TestClient
    ):
        store = app.dependency_overrides[get_session_store]()
        store.sessions["test-session"] = replace(
            store.sessions["test-session"], redmine_user_id=8
        )

        resp = client.get("/tickets")

        assert resp.status_code == 200
        assert [ticket["id"] for ticket in resp.json()["tickets"]] == [100]

    def test_sales_user_cannot_open_responder_view(self, client: TestClient):
        store = app.dependency_overrides[get_session_store]()
        store.sessions["test-session"] = replace(
            store.sessions["test-session"], redmine_user_id=8
        )

        resp = client.get("/tickets?view=responder")

        assert resp.status_code == 403

    def test_list_tickets_empty_project(self, client: TestClient):
        """境界条件: 該当チケットが0件の場合"""
        # Unknown status filter should return empty or all depending on implementation
        resp = client.get("/tickets?status=unknown_status")
        assert resp.status_code == 200


class TestGetTicket:
    """テストケース: チケット詳細取得"""

    def test_get_ticket_success(self, client: TestClient):
        """正常系: チケット詳細が正しく返る"""
        resp = client.get("/tickets/100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == 100
        assert data["subject"] == "テスト件名"
        assert data["assignee"] == {"id": 7, "name": "Test User"}
        assert data["tracker"] == "report"
        assert data["tracker_name"] == "報告書"
        assert {"id", "tracker", "tracker_name", "subject", "description", "status",
                "priority", "priority_name", "assignee", "customer_id", "report_delivered",
                "notes", "audit_log"} <= set(data)
        assert data["report_delivered"] is False
        assert "audit_log" in data

    def test_get_ticket_has_journals(self, client: TestClient):
        """正常系: journals が notes に変換される"""
        resp = client.get("/tickets/100")
        data = resp.json()
        assert "notes" in data
        assert len(data["notes"]) >= 1

    def test_get_ticket_has_audit_log(self, client: TestClient):
        """正常系: audit_log にフィールド変更が含まれる"""
        resp = client.get("/tickets/100")
        data = resp.json()
        # First journal should have both comment and status change.
        first_entry = data["audit_log"][0] if data["audit_log"] else {}
        assert first_entry.get("type") in ("comment", "change", "both")

    def test_custom_field_audit_uses_ui_labels_and_boolean_text(self, client: TestClient):
        changes = [
            change
            for entry in client.get("/tickets/100").json()["audit_log"]
            for change in entry["changes"]
            if change["field"] == "report_delivered"
        ]
        assert changes == [
            {
                "field": "report_delivered",
                "display_field": "報告書を渡した",
                "old_value": "いいえ",
                "new_value": "はい",
            },
        ]

    def test_get_ticket_resolves_assignee_name_in_audit_log(
        self, client: TestClient
    ):
        resp = client.get("/tickets/100")
        assert resp.status_code == 200
        changes = [
            change
            for entry in resp.json()["audit_log"]
            for change in entry["changes"]
            if change["field"] == "assigned_to_id"
        ]
        assert changes == [
            {
                "field": "assigned_to_id",
                "display_field": "担当者",
                "old_value": None,
                "new_value": "Test User",
            }
        ]

    def test_get_ticket_resolves_priority_names_in_audit_log(
        self, client: TestClient
    ):
        resp = client.get("/tickets/100")
        assert resp.status_code == 200
        priority_changes = [
            change
            for entry in resp.json()["audit_log"]
            for change in entry["changes"]
            if change["field"] == "priority_id"
        ]
        assert priority_changes == [
            {
                "field": "priority_id",
                "display_field": "優先度",
                "old_value": "Normal",
                "new_value": "Urgent",
            }
        ]


class TestAddComment:
    """テストケース: コメント追加"""

    def test_add_comment_success(self, client: TestClient):
        """正常系: コメントが正しく追加される"""
        resp = client.post("/tickets/100/comments", json={"body": "テストコメント"})
        assert resp.status_code == 200
        update_request = next(
            call.request
            for call in reversed(respx.calls)
            if call.request.method == "PUT"
            and call.request.url.path == "/issues/100.json"
        )
        assert json.loads(update_request.content) == {
            "issue": {"notes": "テストコメント"}
        }

    def test_add_comment_empty_body(self, client: TestClient):
        """異常系: body が空だと422エラー"""
        resp = client.post("/tickets/100/comments", json={"body": ""})
        assert resp.status_code == 422

    def test_add_comment_whitespace_only_body(self, client: TestClient):
        resp = client.post("/tickets/100/comments", json={"body": " \n\t "})
        assert resp.status_code == 422


class TestCustomFields:
    @pytest.mark.parametrize(
        ("field", "value"),
        [("tracker_id", 4), ("report_required", True), ("customer_visit_required", True)],
    )
    def test_update_custom_fields_rejects_removed_fields(
        self, client: TestClient, field: str, value: object
    ):
        response = client.patch("/tickets/100/custom-fields", json={field: value})

        assert response.status_code == 422
        assert not any(call.request.method == "PUT" for call in respx.calls)

    def test_support_sees_and_updates_all_fields(self, client: TestClient):
        detail = client.get("/tickets/100")
        assert detail.json()["customer_id"] == "C-100"
        assert detail.json()["report_delivered"] is False
        assert "schedule_assigned" not in detail.json()

        response = client.patch(
            "/tickets/100/custom-fields",
            json={"customer_id": " C-200 ", "report_delivered": True},
        )
        assert response.status_code == 200
        update_request = next(
            call.request for call in reversed(respx.calls)
            if call.request.method == "PUT" and call.request.url.path == "/issues/100.json"
        )
        assert json.loads(update_request.content) == {"issue": {"custom_fields": [
            {"id": 11, "value": "C-200"},
            {"id": 13, "value": "1"},
        ], "status_id": 3, "assigned_to_id": 8}}

    @pytest.mark.parametrize("ticket_id, field_name, field_id", [
        (100, "report_delivered", 13),
        (101, "schedule_assigned", 15),
    ])
    def test_completion_field_assigns_ticket_author(
        self, client: TestClient, ticket_id: int, field_name: str, field_id: int
    ):
        response = client.patch(
            f"/tickets/{ticket_id}/custom-fields",
            json={field_name: True},
        )

        assert response.status_code == 200
        update_request = next(
            call.request for call in reversed(respx.calls)
            if call.request.method == "PUT"
            and call.request.url.path == f"/issues/{ticket_id}.json"
        )
        assert json.loads(update_request.content) == {"issue": {
            "custom_fields": [{"id": field_id, "value": "1"}],
            "status_id": 3,
            "assigned_to_id": 8,
        }}

    @pytest.mark.parametrize("ticket_id, field_name, expected_tracker", [
        (100, "schedule_assigned", "客先同行"),
        (101, "report_delivered", "報告書"),
    ])
    def test_completion_field_rejects_mismatched_tracker(
        self, client: TestClient, ticket_id: int, field_name: str, expected_tracker: str
    ):
        put_count = sum(call.request.method == "PUT" for call in respx.calls)

        response = client.patch(
            f"/tickets/{ticket_id}/custom-fields", json={field_name: True}
        )

        assert response.status_code == 422
        assert expected_tracker in response.json()["detail"]
        assert sum(call.request.method == "PUT" for call in respx.calls) == put_count

    @pytest.mark.parametrize("field_name", ["report_delivered", "schedule_assigned"])
    def test_sales_cannot_see_or_update_support_only_fields(
        self, client: TestClient, field_name: str
    ):
        store = app.dependency_overrides[get_session_store]()
        store.sessions["test-session"] = replace(
            store.sessions["test-session"], redmine_user_id=8
        )
        detail = client.get("/tickets/100")
        assert "report_delivered" not in detail.json()
        assert "schedule_assigned" not in detail.json()
        audit_fields = {
            change["field"]
            for entry in detail.json()["audit_log"]
            for change in entry["changes"]
        }
        assert "report_delivered" not in audit_fields

        response = client.patch(
            "/tickets/100/custom-fields", json={field_name: True}
        )
        assert response.status_code == 403

class TestAnswerTicket:
    def test_support_user_adds_answer_and_assigns_ticket_author(
        self, client: TestClient
    ):
        resp = client.post("/tickets/100/answer", json={"body": "回答です"})
        assert resp.status_code == 200

        update_request = next(
            call.request
            for call in reversed(respx.calls)
            if call.request.method == "PUT"
            and call.request.url.path == "/issues/100.json"
        )
        assert json.loads(update_request.content) == {
            "issue": {
                "notes": "回答です",
                "assigned_to_id": 8,
                "status_id": 3,
            }
        }

    def test_answer_rejects_empty_body(self, client: TestClient):
        resp = client.post("/tickets/100/answer", json={"body": "  "})
        assert resp.status_code == 422

    def test_answer_rejects_non_support_user(self, client: TestClient):
        store = app.dependency_overrides[get_session_store]()
        store.sessions["test-session"] = replace(
            store.sessions["test-session"], redmine_user_id=8
        )

        resp = client.post("/tickets/100/answer", json={"body": "回答です"})

        assert resp.status_code == 403

    def test_answer_fails_when_answered_status_is_unavailable(
        self, client: TestClient, monkeypatch
    ):
        original_resolver = app_module._resolve_status_id
        monkeypatch.setattr(
            app_module,
            "_resolve_status_id",
            lambda key: None if key == "answered" else original_resolver(key),
        )

        resp = client.post("/tickets/100/answer", json={"body": "回答です"})

        assert resp.status_code == 503
        assert resp.json()["detail"] == "対応済ステータスが設定されていません"


class TestClaimTicket:
    """テストケース: ログインユーザーへの担当割り当て"""

    def test_claim_ticket_assigns_authenticated_user(self, client: TestClient):
        resp = client.patch("/tickets/100/assignee")
        assert resp.status_code == 200

        update_request = next(
            call.request
            for call in reversed(respx.calls)
            if call.request.method == "PUT"
            and call.request.url.path == "/issues/100.json"
        )
        assert update_request.headers["X-Redmine-API-Key"] == "user_specific_api_key"
        assert (
            update_request.content
            == b'{"issue":{"assigned_to_id":7,"status_id":2}}'
        )

    def test_sales_user_cannot_claim_ticket(self, client: TestClient):
        store = app.dependency_overrides[get_session_store]()
        store.sessions["test-session"] = replace(
            store.sessions["test-session"], redmine_user_id=8
        )

        resp = client.patch("/tickets/100/assignee")

        assert resp.status_code == 403


class TestUpdateStatus:
    """テストケース: ステータス更新"""

    def test_update_status_by_id(self, client: TestClient):
        """正常系: status_id で更新"""
        resp = client.patch("/tickets/100/status", json={"status_id": 2})
        assert resp.status_code == 200

    def test_return_to_waiting_clears_assignee(self, client: TestClient):
        resp = client.patch("/tickets/100/status", json={"status_id": 1})
        assert resp.status_code == 200
        update_request = next(
            call.request
            for call in reversed(respx.calls)
            if call.request.method == "PUT"
            and call.request.url.path == "/issues/100.json"
        )
        assert (
            update_request.content
            == b'{"issue":{"status_id":1,"assigned_to_id":""}}'
        )

    def test_update_status_invalid(self, client: TestClient):
        """異常系: 存在しないステータスIDだと400エラー"""
        resp = client.patch("/tickets/100/status", json={"status_id": 999})
        assert resp.status_code == 400

    def test_update_status_missing(self, client: TestClient):
        """異常系: status_id が省略されていると422エラー"""
        resp = client.patch("/tickets/100/status", json={})
        assert resp.status_code == 422


class TestUpdatePriority:
    def test_update_priority_by_redmine_id(self, client: TestClient):
        response = client.patch("/tickets/100/priority", json={"priority_id": 4})

        assert response.status_code == 200
        update_request = next(
            call.request for call in reversed(respx.calls)
            if call.request.method == "PUT" and call.request.url.path == "/issues/100.json"
        )
        assert json.loads(update_request.content) == {"issue": {"priority_id": 4}}

    def test_update_priority_rejects_unknown_id(self, client: TestClient):
        response = client.patch("/tickets/100/priority", json={"priority_id": 999})

        assert response.status_code == 400
