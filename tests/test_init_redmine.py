"""Tests for the standalone Redmine initialization script."""

import importlib.util
from pathlib import Path

import httpx
import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "init_redmine.py"
spec = importlib.util.spec_from_file_location("init_redmine", SCRIPT)
init_redmine = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(init_redmine)


def client_for(handler):
    return httpx.Client(
        base_url="http://redmine.test",
        transport=httpx.MockTransport(handler),
    )


def test_login_uses_current_user_endpoint_and_returns_api_key():
    def handler(request):
        assert request.url.path == "/users/current.json"
        assert request.headers["Authorization"].startswith("Basic ")
        return httpx.Response(200, json={"user": {"id": 1, "api_key": "secret"}})

    with client_for(handler) as client:
        assert init_redmine._login(client) == "secret"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://localhost:3000", False),
        ("http://127.0.0.1:3000", False),
        ("http://[::1]:3000", False),
        ("https://redmine.example.com", True),
    ],
)
def test_environment_proxy_is_bypassed_only_for_loopback(url, expected):
    assert init_redmine._trust_environment_proxy(url) is expected


def test_login_reports_disabled_rest_api_without_dumping_html(capsys):
    with client_for(lambda request: httpx.Response(404, text="<html>sensitive proxy page</html>")) as client:
        with pytest.raises(SystemExit):
            init_redmine._login(client)

    output = capsys.readouterr().out
    assert "REST API is disabled" in output
    assert "sensitive proxy page" not in output


def test_ensure_trackers_returns_all_portal_tracker_ids():
    def handler(request):
        assert request.url.path == "/trackers.json"
        return httpx.Response(200, json={"trackers": [
            {"id": 3, "name": "問い合わせ"},
            {"id": 4, "name": "報告書"},
            {"id": 5, "name": "客先同行"},
        ]})

    with client_for(handler) as client:
        assert init_redmine.ensure_trackers(client, "api-key") == {
            "問い合わせ": 3,
            "報告書": 4,
            "客先同行": 5,
        }


def test_missing_tracker_does_not_attempt_unsupported_post(capsys):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"trackers": [
            {"id": 3, "name": "問い合わせ"},
        ]})

    with client_for(handler) as client:
        with pytest.raises(SystemExit):
            init_redmine.ensure_trackers(client, "api-key")

    assert [request.method for request in requests] == ["GET"]
    assert "報告書, 客先同行" in capsys.readouterr().out


def test_statuses_support_redmine_61_defaults():
    def handler(request):
        assert request.url.path == "/issue_statuses.json"
        return httpx.Response(
            200,
            json={
                "issue_statuses": [
                    {"id": 1, "name": "New"},
                    {"id": 2, "name": "In Progress"},
                    {"id": 3, "name": "Resolved"},
                    {"id": 4, "name": "Feedback"},
                    {"id": 5, "name": "Closed"},
                    {"id": 6, "name": "Rejected"},
                ]
            },
        )

    with client_for(handler) as client:
        assert init_redmine.check_statuses(client, "api-key") == {
            "open": 1,
            "in_progress": 2,
            "answered": 3,
            "pending_close": 6,
            "closed": 5,
        }


def test_statuses_support_portal_workflow_names():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "issue_statuses": [
                    {"id": 1, "name": "対応待ち"},
                    {"id": 2, "name": "In Progress"},
                    {"id": 3, "name": "対応済"},
                    {"id": 5, "name": "Closed"},
                    {"id": 6, "name": "Rejected"},
                ]
            },
        )

    with client_for(handler) as client:
        mapping = init_redmine.check_statuses(client, "api-key")
        assert mapping["open"] == 1
        assert mapping["answered"] == 3
