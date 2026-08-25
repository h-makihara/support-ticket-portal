"""Unit tests for backend helper functions."""

from backend.app import (
    _journals_to_notes,
    _journals_to_audit,
    _issue_to_dict,
    _field_display_name,
    _latest_support_responder,
)


class TestIssueToDict:
    """テストケース: issue dict の変換"""

    def test_basic_conversion(self):
        """正常系: Redmine issue が期待する形式に変換される"""
        redmine_issue = {
            "id": 123,
            "subject": "Test Subject",
            "description": "Test Description",
            "tracker": {"id": 3, "name": "問い合わせ"},
            "status": {"id": 1, "name": "New"},
            "priority": {"id": 3, "name": "Normal"},
            "assigned_to": {"id": 7, "name": "Support Agent"},
            "created_on": "2024-01-01T00:00:00Z",
            "updated_on": "2024-01-01T00:00:00Z",
        }
        result = _issue_to_dict(redmine_issue)
        assert result["id"] == 123
        assert result["subject"] == "Test Subject"
        assert result["status"] == "New"
        assert result["priority"] == 3
        assert result["assignee"] == {"id": 7, "name": "Support Agent"}

    def test_handles_missing_optional_fields(self):
        """正常系: オプションフィールドがない場合でも動作する"""
        redmine_issue = {
            "id": 456,
            "subject": "",
            "description": "",
            "tracker": {"id": 3, "name": "問い合わせ"},
            "status": {"id": 1, "name": "New"},
            "priority": {"id": 3, "name": "Normal"},
        }
        result = _issue_to_dict(redmine_issue)
        assert result["created_on"] == ""
        assert result["assignee"] is None

    def test_customer_visit_normalizes_missing_visit_mode_to_none(self):
        redmine_issue = {
            "id": 457,
            "subject": "Legacy visit",
            "description": "",
            "tracker": {"id": 5, "name": "客先同行"},
            "status": {"id": 1, "name": "New"},
            "priority": {"id": 3, "name": "Normal"},
            "custom_fields": [{"id": 17, "name": "同行方法", "value": ""}],
        }

        assert _issue_to_dict(redmine_issue)["visit_mode"] is None


class TestJournalsToNotes:
    """テストケース: journals → notes 変換"""

    def test_converts_journals_to_notes(self):
        """正常系: journal entries が notes に変換される"""
        journals = [
            {
                "id": 1,
                "notes": "Initial comment",
                "user": {"name": "admin"},
                "created_on": "2024-01-01T00:00:00Z",
            },
            {
                "id": 2,
                "notes": "",
                "user": {"name": "user1"},
                "created_on": "2024-01-02T00:00:00Z",
            },
        ]
        notes = _journals_to_notes(journals)
        # Only entries with non-empty notes should be included.
        assert len(notes) == 1
        assert notes[0]["body"] == "Initial comment"
        assert notes[0]["author"] == "admin"

    def test_empty_journals_returns_empty_list(self):
        """境界条件: journals が空の場合、空リストが返る"""
        notes = _journals_to_notes([])
        assert notes == []


class TestJournalsToAudit:
    """テストケース: journals → audit log 変換"""

    def test_comment_only_entry(self):
        """正常系: コメントのみを含む journal が正しく変換される"""
        journals = [
            {
                "notes": "Just a comment",
                "user": {"name": "sales_user"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [],
            }
        ]
        entries = _journals_to_audit(journals)
        assert len(entries) == 1
        assert entries[0]["type"] == "comment"
        assert entries[0]["comment"] == "Just a comment"

    def test_change_only_entry(self):
        """正常系: フィールド変更のみを含む journal が正しく変換される"""
        journals = [
            {
                "notes": "",
                "user": {"name": "admin"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [
                    {
                        "prop_key": "status_id",
                        "old_value": "New",
                        "new_value": "In Progress",
                    }
                ],
            }
        ]
        entries = _journals_to_audit(journals)
        assert len(entries) == 1
        assert entries[0]["type"] == "change"
        assert len(entries[0]["changes"]) == 1
        assert entries[0]["changes"][0]["field"] == "status_id"

    def test_assignee_ids_are_converted_to_user_names(self):
        journals = [
            {
                "notes": "",
                "user": {"name": "support_user"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [
                    {
                        "prop_key": "assigned_to_id",
                        "old_value": None,
                        "new_value": "6",
                    }
                ],
            }
        ]
        entries = _journals_to_audit(journals, {6: "サポート 太郎"})
        change = entries[0]["changes"][0]
        assert change["old_value"] is None
        assert change["new_value"] == "サポート 太郎"

    def test_status_ids_are_converted_to_status_names(self):
        journals = [
            {
                "notes": "",
                "user": {"name": "support_user"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [
                    {
                        "prop_key": "status_id",
                        "old_value": "2",
                        "new_value": "3",
                    }
                ],
            }
        ]
        entries = _journals_to_audit(
            journals,
            status_names={2: "対応中", 3: "対応済"},
        )
        change = entries[0]["changes"][0]
        assert change["old_value"] == "対応中"
        assert change["new_value"] == "対応済"

    def test_priority_ids_are_converted_to_priority_names(self):
        journals = [
            {
                "notes": "",
                "user": {"name": "support_user"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [
                    {
                        "prop_key": "priority_id",
                        "old_value": "2",
                        "new_value": "4",
                    }
                ],
            }
        ]

        entries = _journals_to_audit(
            journals,
            priority_names={2: "標準", 4: "緊急"},
        )

        change = entries[0]["changes"][0]
        assert change["display_field"] == "優先度"
        assert change["old_value"] == "標準"
        assert change["new_value"] == "緊急"

    def test_custom_field_ids_and_boolean_values_are_displayed_as_ui_text(self):
        journals = [{
            "notes": "",
            "user": {"name": "support_user"},
            "created_on": "2024-01-01T00:00:00Z",
            "details": [{
                "property": "cf",
                "name": "13",
                "old_value": "0",
                "new_value": "1",
            }],
        }]
        entries = _journals_to_audit(
            journals,
            custom_fields={13: {
                "key": "report_delivered",
                "label": "報告書を渡した",
                "boolean": True,
                "hidden": False,
            }},
        )
        assert entries[0]["changes"] == [{
            "field": "report_delivered",
            "display_field": "報告書を渡した",
            "old_value": "いいえ",
            "new_value": "はい",
        }]

    def test_hidden_custom_field_changes_are_removed(self):
        journals = [{
            "notes": "",
            "user": {"name": "support_user"},
            "created_on": "2024-01-01T00:00:00Z",
            "details": [{
                "property": "cf", "name": "13", "old_value": "0", "new_value": "1",
            }],
        }]
        entries = _journals_to_audit(
            journals,
            custom_fields={13: {
                "key": "report_delivered",
                "label": "報告書を渡した",
                "boolean": True,
                "hidden": True,
            }},
        )
        assert entries == []

    def test_both_comment_and_changes(self):
        """正常系: コメントと変更の両方を含む journal が正しく変換される"""
        journals = [
            {
                "notes": "Updated priority and status",
                "user": {"name": "manager"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [
                    {
                        "prop_key": "status_id",
                        "old_value": "New",
                        "new_value": "In Progress",
                    },
                    {
                        "prop_key": "priority_id",
                        "old_value": "2",
                        "new_value": "1",
                    }
                ],
            }
        ]
        entries = _journals_to_audit(journals)
        assert len(entries) == 1
        assert entries[0]["type"] == "both"
        assert entries[0]["comment"] == "Updated priority and status"
        assert len(entries[0]["changes"]) == 2

    def test_empty_journal_skipped(self):
        """正常系: コメントも変更もない journal はスキップされる"""
        journals = [
            {
                "notes": "",
                "user": {"name": "system"},
                "created_on": "2024-01-01T00:00:00Z",
                "details": [],
            }
        ]
        entries = _journals_to_audit(journals)
        assert len(entries) == 0


class TestFieldDisplayName:
    """テストケース: フィールド名表示マッピング"""

    def test_known_fields_mapped(self):
        """正常系: 既知のフィールド名が日本語ラベルに変換される"""
        assert _field_display_name("status_id") == "ステータス"
        assert _field_display_name("priority") == "優先度"
        assert _field_display_name("assigned_to_id") == "担当者"

    def test_unknown_fields_returned_as_is(self):
        """正常系: 未知のフィールド名はそのまま返される"""
        assert _field_display_name("unknown_field") == "unknown_field"


def test_latest_support_responder_uses_most_recent_support_journal():
    issue = {"journals": [
        {"created_on": "2026-01-01T10:00:00Z", "user": {"id": 7, "name": "Support A"}},
        {"created_on": "2026-01-01T11:00:00Z", "user": {"id": 8, "name": "Sales"}},
        {"created_on": "2026-01-01T12:00:00Z", "user": {"id": 9, "name": "Support B"}},
    ]}

    assert _latest_support_responder(issue, {7, 9}) == {
        "id": 9,
        "name": "Support B",
    }
