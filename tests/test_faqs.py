"""FAQ API tests backed by mocked Redmine Wiki endpoints."""

from dataclasses import replace
import json
import re

import httpx
from fastapi.testclient import TestClient
import respx

from backend.app import app, get_session_store


QUESTION = "報告書が欲しいです"
ANSWER = "報告書チケットを作成し、対応情報を更新してください"


def wiki_page(title: str, question: str = QUESTION, answer: str = ANSWER, version: int = 1):
    return {
        "title": title,
        "text": f"Q: {question}\n\nA:\n{answer}",
        "version": version,
        "author": {"id": 7, "name": "Test User"},
        "created_on": "2026-08-01T00:00:00Z",
        "updated_on": "2026-08-02T00:00:00Z",
    }


def register_faq_routes(pages: dict[str, dict]):
    respx.get("http://test-redmine:3000/projects/99/wiki/index.json").mock(
        return_value=httpx.Response(
            200,
            json={"wiki_pages": [{"title": title} for title in pages]},
        )
    )

    def get_page(request: httpx.Request):
        title = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
        page = pages.get(title)
        return httpx.Response(200, json={"wiki_page": page}) if page else httpx.Response(404)

    def put_page(request: httpx.Request):
        title = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
        payload = json.loads(request.content)["wiki_page"]
        previous = pages.get(title)
        if previous and payload.get("version") != previous["version"]:
            return httpx.Response(409)
        pages[title] = wiki_page(
            title,
            question=payload["text"].split("\n", 1)[0].removeprefix("Q: "),
            answer=payload["text"].split("\n\nA:\n", 1)[1],
            version=(previous["version"] + 1) if previous else 1,
        )
        return httpx.Response(204 if previous else 201)

    def delete_page(request: httpx.Request):
        title = request.url.path.rsplit("/", 1)[-1].removesuffix(".json")
        return httpx.Response(204) if pages.pop(title, None) else httpx.Response(404)

    path = re.compile(r"http://test-redmine:3000/projects/99/wiki/FAQ_[A-Za-z0-9_-]+\.json")
    respx.get(url__regex=path).mock(side_effect=get_page)
    respx.put(url__regex=path).mock(side_effect=put_page)
    respx.delete(url__regex=path).mock(side_effect=delete_page)


def test_sales_can_list_search_and_view_faqs(client: TestClient):
    store = app.dependency_overrides[get_session_store]()
    store.sessions["test-session"] = replace(store.sessions["test-session"], redmine_user_id=8)
    pages = {
        "FAQ_report_request": wiki_page("FAQ_report_request"),
        "FAQ_visit": wiki_page("FAQ_visit", "客先に同行してほしいです", "客先同行チケットを作成し、対応情報を更新してください"),
        "Home": {"title": "Home", "text": "通常のWikiページ"},
    }
    register_faq_routes(pages)

    response = client.get("/faqs", params={"q": "報告書"})

    assert response.status_code == 200
    assert response.json()["pagination"]["total_count"] == 1
    assert response.json()["faqs"][0]["question"] == QUESTION
    detail = client.get("/faqs/report_request")
    assert detail.status_code == 200
    assert detail.json()["answer"] == ANSWER


def test_sales_cannot_create_update_or_delete_faqs(client: TestClient):
    store = app.dependency_overrides[get_session_store]()
    store.sessions["test-session"] = replace(store.sessions["test-session"], redmine_user_id=8)

    assert client.post("/faqs", json={"question": QUESTION, "answer": ANSWER}).status_code == 403
    assert client.put("/faqs/report_request", json={"question": QUESTION, "answer": ANSWER, "version": 1}).status_code == 403
    assert client.delete("/faqs/report_request").status_code == 403


def test_support_can_create_update_and_delete_faq(client: TestClient):
    pages: dict[str, dict] = {}
    register_faq_routes(pages)

    created = client.post("/faqs", json={"question": QUESTION, "answer": ANSWER})
    assert created.status_code == 201
    faq = created.json()
    assert faq["question"] == QUESTION

    updated = client.put(
        f"/faqs/{faq['id']}",
        json={"question": "更新した質問", "answer": "更新した回答", "version": faq["version"]},
    )
    assert updated.status_code == 200
    assert updated.json()["question"] == "更新した質問"
    assert updated.json()["version"] == 2

    deleted = client.delete(f"/faqs/{faq['id']}")
    assert deleted.status_code == 200
    assert pages == {}


def test_admin_can_create_faq_without_project_role(client: TestClient):
    store = app.dependency_overrides[get_session_store]()
    store.sessions["test-session"] = replace(
        store.sessions["test-session"], redmine_user_id=42, is_admin=True
    )
    pages: dict[str, dict] = {}
    register_faq_routes(pages)

    response = client.post("/faqs", json={"question": QUESTION, "answer": ANSWER})

    assert response.status_code == 201
