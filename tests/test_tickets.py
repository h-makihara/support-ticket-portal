"""Unit tests for ticket CRUD endpoints."""

import respx
from fastapi.testclient import TestClient


class TestCreateTicket:
    """テストケース: チケット作成"""

    def test_create_ticket_success(self, client: TestClient):
        """正常系: チケットが正しく作成される"""
        payload = {
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

    def test_create_ticket_missing_subject(self, client: TestClient):
        """異常系: subject が省略されていると422エラー"""
        payload = {
            "description": "説明だけ",
        }
        resp = client.post("/tickets", json=payload)
        assert resp.status_code == 422

    def test_create_ticket_missing_description(self, client: TestClient):
        """異常系: description が省略されていると422エラー"""
        payload = {
            "subject": "件名だけ",
        }
        resp = client.post("/tickets", json=payload)
        assert resp.status_code == 422

    def test_create_ticket_with_tracker_id(self, client: TestClient):
        """正常系: tracker_id を指定して作成"""
        payload = {
            "subject": "テスト",
            "description": "テスト本文",
            "tracker_id": 3,
        }
        resp = client.post("/tickets", json=payload)
        assert resp.status_code == 200


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
        assert data["tickets"][0]["status"] == "新規"

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
        assert data["pagination"]["total_count"] == 2

        issues_request = next(
            call.request
            for call in respx.calls
            if call.request.url.path == "/issues.json"
        )
        assert issues_request.url.params["status_id"] == "open"

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


class TestAddComment:
    """テストケース: コメント追加"""

    def test_add_comment_success(self, client: TestClient):
        """正常系: コメントが正しく追加される"""
        resp = client.post("/tickets/100/comments", json={"body": "テストコメント"})
        assert resp.status_code == 200

    def test_add_comment_empty_body(self, client: TestClient):
        """異常系: body が空だと422エラー"""
        resp = client.post("/tickets/100/comments", json={"body": ""})
        assert resp.status_code == 422


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


class TestUpdateStatus:
    """テストケース: ステータス更新"""

    def test_update_status_by_id(self, client: TestClient):
        """正常系: status_id で更新"""
        resp = client.patch("/tickets/100/status", json={"status_id": 2})
        assert resp.status_code == 200

    def test_additional_question_clears_assignee(self, client: TestClient):
        resp = client.patch("/tickets/100/status", json={"status_id": 4})
        assert resp.status_code == 200
        update_request = next(
            call.request
            for call in reversed(respx.calls)
            if call.request.method == "PUT"
            and call.request.url.path == "/issues/100.json"
        )
        assert (
            update_request.content
            == b'{"issue":{"status_id":4,"assigned_to_id":""}}'
        )

    def test_update_status_invalid(self, client: TestClient):
        """異常系: 存在しないステータスIDだと400エラー"""
        resp = client.patch("/tickets/100/status", json={"status_id": 999})
        assert resp.status_code == 400

    def test_update_status_missing(self, client: TestClient):
        """異常系: status_id が省略されていると422エラー"""
        resp = client.patch("/tickets/100/status", json={})
        assert resp.status_code == 422
