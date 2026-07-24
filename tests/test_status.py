"""Unit tests for status-related functionality."""

from fastapi.testclient import TestClient
from src.backend.app import _fetch_statuses, _resolve_status_id, _status_by_key


class TestStatusOptions:
    """テストケース: ステータスオプション取得"""

    def test_status_options_returns_list(self, client: TestClient):
        """正常系: /status/options がリストを返す"""
        resp = client.get("/status/options")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have at least 4 statuses.
        assert len(data) >= 4

    def test_status_options_has_id_and_label(self, client: TestClient):
        """正常系: ステータスに id と label が含まれる"""
        resp = client.get("/status/options")
        data = resp.json()
        for status in data:
            assert "id" in status
            assert "label" in status


class TestStatusResolution:
    """テストケース: ステータス解決ロジック"""

    def test_resolve_open_status(self, client: TestClient):
        """正常系: open キーが New(ID=1) に解決される"""
        # Status cache should be populated by startup event.
        result = _resolve_status_id("open")
        assert result == 1

    def test_resolve_in_progress_status(self, client: TestClient):
        """正常系: in_progress キーが In Progress(ID=2) に解決される"""
        result = _resolve_status_id("in_progress")
        assert result == 2

    def test_resolve_closed_status(self, client: TestClient):
        """正常系: closed キーが クローズ(ID=5) に解決される"""
        result = _resolve_status_id("closed")
        assert result == 5

    def test_resolve_additional_question_status(self, client: TestClient):
        """正常系: additional_question が 追加質問(ID=4) に解決される"""
        result = _resolve_status_id("additional_question")
        assert result == 4

    def test_resolve_unknown_status_returns_none(self, client: TestClient):
        """正常系: 未知のキーは None を返す"""
        result = _resolve_status_id("unknown_key_12345")
        assert result is None
