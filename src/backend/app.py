"""FastAPI wrapper around Redmine for MVP ticket portal."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

# ── OpenTelemetry setup ─────────────────────────────────────────────

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317")

resource = Resource.create({
    "service.name": "ticket-portal-backend",
    "service.version": "0.1.0",
})

trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer("ticket-portal")

span_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(span_exporter))

# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(title="Redmine Ticket Portal API")

# CORS - explicit origins (no "*" + credentials=True conflict)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# FastAPI auto-instrumentation (covers route handlers, DB spans etc.)
FastAPIInstrumentor.instrument_app(app)

# httpx auto-instrumentation (covers outgoing Redmine requests)
HTTPXClientInstrumentor().instrument()

# Configuration
REDMINE_BASE_URL = os.getenv("REDMINE_BASE_URL", "http://redmine:3000")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY", "")
REDMINE_PROJECT_ID = os.getenv("REDMINE_PROJECT_ID", "")
REDMINE_TRACKER_ID = os.getenv("REDMINE_TRACKER_ID", "3")

if not REDMINE_API_KEY:
    raise RuntimeError("REDMINE_API_KEY must be set")
if not REDMINE_PROJECT_ID:
    raise RuntimeError("REDMINE_PROJECT_ID must be set")

HEADERS = {"X-Redmine-API-Key": REDMINE_API_KEY, "Content-Type": "application/json"}

# ── Status cache ────────────────────────────────────────────────────
# Populated at startup by querying Redmine's /issue_statuses.json.
# _status_by_name:  Redmine status name  -> int id
# _status_by_id:    int id              -> Redmine status name
# _status_by_id:    int id              -> Redmine status name
# _status_by_key:   English filter key  -> int id
_status_by_name: Dict[str, int] = {}
_status_by_id: Dict[int, str] = {}
_status_by_key: Dict[str, int] = {}

# Mapping: English filter key (used by frontend) → set of Redmine slug/name matches.
# This is filled dynamically at startup by querying /issue_statuses.json.
_ENGLISH_KEY_MATCHERS: Dict[str, set] = {
    "open":        {"new", "open"},
    "in_progress": {"in_progress", "in progress", "progress"},
    "feedback":    {"reopened", "re_opened", "feedback", "additional_question"},
    "closed":      {"closed"},
}

# Default fallback (when Redmine is not reachable at startup):
_DEFAULT_KEY_FALLBACK: Dict[str, int] = {
    "open":        1,   # New
    "in_progress": 2,   # In Progress
    "feedback":    3,   # Reopened
    "closed":      4,   # Closed
}


async def _fetch_statuses() -> None:
    """Query Redmine /issue_statuses.json and populate caches."""
    try:
        async with httpx.AsyncClient(
            base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0
        ) as c:
            r = await c.get("/issue_statuses.json")
        if r.status_code != 200:
            raise RuntimeError(f"GET issue_statuses failed: {r.status_code}")

        for s in r.json().get("issue_statuses", []):
            sid = int(s["id"])
            name = s.get("name", "")
            slug = s.get("slug", "").lower()
            _status_by_name[name] = sid
            _status_by_id[sid] = name

            # Map English filter keys if the slug/name matches.
            for key, aliases in _ENGLISH_KEY_MATCHERS.items():
                if slug in aliases or name.lower() in aliases:
                    _status_by_key[key] = sid
                    break
            else:
                # Fallback: use slug as-is if it looks like an English key.
                if slug and slug in _ENGLISH_KEY_MATCHERS:
                    _status_by_key[slug] = sid

    except Exception as e:
        print(f"[WARN] Failed to fetch statuses from Redmine: {e}")
        print(f"       Using default fallback mapping: {_DEFAULT_KEY_FALLBACK}")
        _status_by_key.update(_DEFAULT_KEY_FALLBACK)
        # Populate _status_by_id with defaults so /status/options works
        for key, sid in _DEFAULT_KEY_FALLBACK.items():
            _status_by_id[sid] = key


@app.on_event("startup")
async def startup():
    await _fetch_statuses()
    print(f"[INFO] Loaded statuses by name: {_status_by_name}")
    print(f"[INFO] Loaded status key map:   {_status_by_key}")
    print(f"[INFO] Loaded status ID→name:  {_status_by_id}")

    print(f"[INFO] Loaded status key map: {_status_by_key}")


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0)


# ── Helpers ─────────────────────────────────────────────────────────

def _issue_to_dict(i: Dict[str, Any]) -> Dict[str, Any]:
    """Extract common fields from a Redmine issue dict."""
    return {
        "id": i["id"],
        "subject": i.get("subject", ""),
        "description": i.get("description", ""),
        "status": i["status"]["name"],
        "priority": int(i["priority"]["id"]),
        "created_on": i.get("created_on", ""),
        "updated_on": i.get("updated_on", ""),
    }


def _journals_to_notes(journals: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convert Redmine journals to our notes format."""
    notes: List[Dict[str, str]] = []
    for j in journals:
        body = j.get("notes", "")
        if not body:
            continue  # skip journal entries without text (only status/field changes)
        author_obj = j.get("user")
        author_name = ""
        if isinstance(author_obj, dict):
            author_name = author_obj.get("name", "")
        elif isinstance(author_obj, str):
            author_name = author_obj
        notes.append({
            "body": body,
            "author": author_name,
            "created_on": j.get("created_on", ""),
        })
    return notes


# Field name mapping for audit log display.
_FIELD_NAME_MAP: Dict[str, str] = {
    "tracker": "トラッカー",
    "status": "ステータス",
    "priority": "優先度",
    "category": "カテゴリ",
    "assigned_to": "担当者",
    "subject": "件名",
    "description": "説明",
    "done_ratio": "進捗率",
    "estimated_hours": "見積もり時間",
    "spent_hours": "実費時間",
    "due_date": "期日",
}


def _field_display_name(field: str) -> str:
    """Map Redmine field name to display label."""
    # Remove trailing _id for user-friendly names.
    clean = field.rstrip("_id") if field.endswith("_id") else field
    return _FIELD_NAME_MAP.get(clean, field)


def _journals_to_audit(journals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Redmine journals to audit log entries.

    Each journal entry becomes a dict with:
      type  : "comment" | "change" | "both"
      author: user name
      created_on: timestamp
      comment: text (if any)
      changes: list of field change dicts (if any)
    """
    entries: List[Dict[str, Any]] = []
    for j in journals:
        body = j.get("notes", "")
        details = j.get("details", [])
        author_obj = j.get("user")
        author_name = ""
        if isinstance(author_obj, dict):
            author_name = author_obj.get("name", "")
        elif isinstance(author_obj, str):
            author_name = author_obj

        entry: Dict[str, Any] = {
            "author": author_name,
            "created_on": j.get("created_on", ""),
        }

        has_comment = bool(body)
        has_changes = len(details) > 0

        if has_comment and has_changes:
            entry["type"] = "both"
            entry["comment"] = body
            entry["changes"] = [
                {
                    "field": d.get("prop_key", ""),
                    "display_field": _field_display_name(d.get("prop_key", "")),
                    "old_value": d.get("old_value"),
                    "new_value": d.get("new_value"),
                }
                for d in details
            ]
        elif has_comment:
            entry["type"] = "comment"
            entry["comment"] = body
            entry["changes"] = []
        elif has_changes:
            entry["type"] = "change"
            entry["changes"] = [
                {
                    "field": d.get("prop_key", ""),
                    "display_field": _field_display_name(d.get("prop_key", "")),
                    "old_value": d.get("old_value"),
                    "new_value": d.get("new_value"),
                }
                for d in details
            ]
        else:
            # Journal with no notes and no details -- skip it.
            continue

        entries.append(entry)
    return entries


def _resolve_status_id(status_key: str) -> Optional[int]:
    """Resolve an English status filter key to a Redmine status ID."""
    sid = _status_by_key.get(status_key.lower())
    if sid is not None:
        return sid
    # Also try matching against the Redmine name directly (case-insensitive).
    for name, n_sid in _status_by_name.items():
        if name.lower() == status_key.lower():
            return n_sid
    return None


# ── Endpoints ───────────────────────────────────────────────────────

@app.post("/tickets")
async def create_ticket(request: Request):
    with tracer.start_as_current_span("create_ticket") as span:
        raw = await request.json()
        span.set_attribute("request.subject", raw.get("subject"))

        subject = raw.get("subject")
        description = raw.get("description")
        priority = raw.get("priority")
        tracker_id = raw.get("tracker_id")

        if not subject or not description:
            return JSONResponse(
                status_code=422,
                content={"detail": "subject and description are required"},
            )

        payload = {
            "issue": {
                "project_id": int(REDMINE_PROJECT_ID),
                "subject": subject,
                "description": description,
            }
        }
        if priority is not None:
            payload["issue"]["priority_id"] = priority
        if tracker_id is not None:
            payload["issue"]["tracker_id"] = tracker_id

        async with _client() as c:
            r = await c.post("/issues.json", json=payload)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 201:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            issue = r.json()["issue"]
            return _issue_to_dict(issue)


@app.get("/tickets")
async def list_tickets(request: Request):
    with tracer.start_as_current_span("list_tickets") as span:
        qs = dict(request.query_params)
        status_key = qs.get("status", "")
        if status_key:
            span.set_attribute("filter.status", status_key)

        # Pagination parameters (Redmine API supports limit/offset)
        try:
            limit = int(qs.get("limit", 100))
            offset = int(qs.get("offset", 0))
        except ValueError:
            limit = 100
            offset = 0

        # Clamp to reasonable bounds
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        params: Dict[str, Any] = {"project_id": REDMINE_PROJECT_ID}

        # Translate frontend's English status key → Redmine status_id for filtering.
        if status_key:
            sid = _resolve_status_id(status_key)
            if sid is not None:
                params["status_id"] = sid
            else:
                print(f"[WARN] Unknown status filter '{status_key}', no mapping in {_status_by_key}")

        # Add pagination to Redmine query
        params["limit"] = limit
        params["offset"] = offset

        async with _client() as c:
            r = await c.get("/issues.json", params=params)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 200:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})

            issues = r.json()["issues"]
            total_count = r.json().get("total_count", len(issues))
            result = [_issue_to_dict(i) for i in issues]
            span.set_attribute("result.count", len(result))

            return {
                "tickets": result,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_count": total_count,
                    "has_more": (offset + len(issues)) < total_count,
                },
            }


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    with tracer.start_as_current_span("get_ticket") as span:
        span.set_attribute("ticket.id", ticket_id)
        async with _client() as c:
            # include=journals fetches comment history
            r = await c.get(f"/issues/{ticket_id}.json", params={"include": "journals"})
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 200:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            i = r.json()["issue"]
            data = _issue_to_dict(i)
            # Full audit log with comments + field changes.
            data["audit_log"] = _journals_to_audit(i.get("journals", []))
            # Also provide backward-compatible notes list.
            data["notes"] = _journals_to_notes(i.get("journals", []))
            return data


@app.post("/tickets/{ticket_id}/comments")
async def add_comment(ticket_id: int, request: Request):
    with tracer.start_as_current_span("add_comment") as span:
        span.set_attribute("ticket.id", ticket_id)
        raw = await request.json()
        body = raw.get("body", "")
        if not body:
            return JSONResponse(status_code=422, content={"detail": "body is required"})
        payload = {"issue": {"notes": body}}
        async with _client() as client:
            r = await client.put(f"/issues/{ticket_id}.json", json=payload)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 200:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            return {"detail": "Comment added"}


@app.patch("/tickets/{ticket_id}/status")
async def update_status(ticket_id: int, request: Request):
    with tracer.start_as_current_span("update_status") as span:
        span.set_attribute("ticket.id", ticket_id)
        raw = await request.json()
        status_value = raw.get("status_id", "")
        if not status_value:
            return JSONResponse(status_code=422, content={"detail": "status_id is required"})

        # Accept either a numeric ID or an English filter key.
        sid: Optional[int] = None
        try:
            sid = int(status_value)
        except (ValueError, TypeError):
            sid = _resolve_status_id(str(status_value))

        if sid is None:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Unknown status value: {status_value}"},
            )

        span.set_attribute("new.status_id", sid)
        payload = {"issue": {"status_id": sid}}
        async with _client() as client:
            r = await client.put(f"/issues/{ticket_id}.json", json=payload)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 200:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            return {"detail": "Status updated"}


@app.get("/status/options")
async def status_options():
    """Return all Redmine issue statuses for frontend dropdowns."""
    result = []
    for sid, name in sorted(_status_by_id.items()):
        result.append({"id": sid, "label": name})
    return result
