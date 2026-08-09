"""FastAPI wrapper around Redmine for MVP ticket portal."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx
from pydantic import BaseModel
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from backend.auth import SessionData, SessionStore, authenticate_with_redmine

logger = logging.getLogger(__name__)


# Keep DEBUG records available to the local Collector. The Collector applies the
# environment-wide INFO threshold and owns the attribute-based DEBUG exception.
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG").upper()
logging.getLogger().setLevel(getattr(logging, LOG_LEVEL, logging.DEBUG))


class _ExcludeOpenTelemetryInternalLogs(logging.Filter):
    """Prevent exporter failures from recursively exporting themselves."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith("opentelemetry")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await _fetch_statuses()
    logger.info(
        "Backend started for Redmine project %s with %d status mappings",
        REDMINE_PROJECT_ID,
        len(_status_by_key),
    )
    yield
    await session_store.close()
    if logger_provider is not None:
        logger_provider.shutdown()
    if tracer_provider is not None:
        tracer_provider.shutdown()


# ── OpenTelemetry setup ─────────────────────────────────────────────

OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
OTEL_ENDPOINT = OTEL_ENDPOINT.rstrip("/")
OTEL_DISABLED = os.getenv("OTEL_SDK_DISABLED", "false").lower() in ("1", "true", "yes")

resource = Resource.create({
    "service.name": "ticket-portal-backend",
    "service.version": "0.4.0",
})

tracer_provider: Optional[TracerProvider] = None
logger_provider: Optional[LoggerProvider] = None

if not OTEL_DISABLED:
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{OTEL_ENDPOINT}/v1/traces"))
    )

    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{OTEL_ENDPOINT}/v1/logs"))
    )
    otel_log_handler = LoggingHandler(
        level=logging.DEBUG, logger_provider=logger_provider
    )
    otel_log_handler.addFilter(_ExcludeOpenTelemetryInternalLogs())
    logging.getLogger().addHandler(otel_log_handler)

tracer = trace.get_tracer("ticket-portal")

# ── App ─────────────────────────────────────────────────────────────

app = FastAPI(title="Redmine Ticket Portal API", lifespan=lifespan)

# CORS - explicit origins (no "*" + credentials=True conflict)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3001").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# FastAPI auto-instrumentation (covers route handlers, DB spans etc.)
FastAPIInstrumentor.instrument_app(app)

# httpx auto-instrumentation (covers outgoing Redmine requests)
HTTPXClientInstrumentor().instrument()

# Configuration
REDMINE_BASE_URL = os.getenv("REDMINE_BASE_URL", "http://redmine:3000")
REDMINE_API_KEY = os.getenv("REDMINE_API_KEY", "")
REDMINE_PROJECT_ID = os.getenv("REDMINE_PROJECT_ID", "")
REDMINE_TRACKER_ID = os.getenv("REDMINE_TRACKER_ID", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "session_id")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() in ("1", "true", "yes")
SESSION_MAX_AGE_SECONDS = 21_600

if not REDMINE_API_KEY:
    raise RuntimeError("REDMINE_API_KEY must be set")
if not REDMINE_PROJECT_ID:
    raise RuntimeError("REDMINE_PROJECT_ID must be set")
if not REDMINE_TRACKER_ID:
    raise RuntimeError("REDMINE_TRACKER_ID must be set")

HEADERS = {"X-Redmine-API-Key": REDMINE_API_KEY, "Content-Type": "application/json"}
session_store = SessionStore(REDIS_URL)

# ── Status cache ────────────────────────────────────────────────────
# Populated at startup by querying Redmine's /issue_statuses.json.
# _status_by_name:  Redmine status name  -> int id
# _status_by_id:    int id              -> Redmine status name
# _status_by_key:   English filter key  -> int id
_status_by_name: Dict[str, int] = {}
_status_by_id: Dict[int, str] = {}
_status_by_key: Dict[str, int] = {}

ROLE_SALES = "sales"
ROLE_SUPPORT = "support"
ROLE_ADMIN = "admin"
_ROLE_BY_REDMINE_NAME = {
    "営業担当者": ROLE_SALES,
    "サポート担当者": ROLE_SUPPORT,
}

CUSTOM_FIELD_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "customer_id": {"name": "顧客ID", "label": "顧客ID", "boolean": False, "support_only": False},
    "report_required": {"name": "報告書要否", "label": "報告書が必要", "boolean": True, "support_only": False},
    "report_delivered": {"name": "報告書渡し済み", "label": "報告書を渡した", "boolean": True, "support_only": True},
    "customer_visit_required": {"name": "客先同行要否", "label": "客先同行が必要", "boolean": True, "support_only": False},
    "schedule_assigned": {"name": "予定・担当者アサイン済み", "label": "予定・担当者をアサインした", "boolean": True, "support_only": True},
}

PRIORITY_ESCALATION_FIELDS = frozenset(
    {"report_required", "customer_visit_required"}
)
AUTHOR_REASSIGNMENT_FIELDS = frozenset(
    {"report_delivered", "schedule_assigned"}
)

FAQ_PAGE_PREFIX = "FAQ_"
FAQ_TEXT_PATTERN = re.compile(r"\AQ: (?P<question>[^\r\n]+)\r?\n\r?\nA:\r?\n(?P<answer>[\s\S]*)\Z")

# Mapping: English filter key (used by frontend) → set of Redmine slug/name matches.
# This is filled dynamically at startup by querying /issue_statuses.json.
_ENGLISH_KEY_MATCHERS: Dict[str, set] = {
    "open":        {"new", "open", "新規", "対応待ち"},
    "in_progress": {"in_progress", "in progress", "progress", "進行中", "対応中"},
    "answered": {"resolved", "answered", "回答済", "対応済"},
    "pending_close": {"rejected", "pending_close", "クローズ待ち"},
    "closed":      {"closed", "終了", "クローズ"},
}

# Redmine 6.1 default fallback (when Redmine is not reachable at startup):
_DEFAULT_KEY_FALLBACK: Dict[str, int] = {
    "open":        1,   # New
    "in_progress": 2,   # In Progress
    "answered":    3,   # Resolved
    "pending_close": 6,  # Rejected
    "closed":      5,   # Closed
}


async def _fetch_statuses() -> None:
    """Query Redmine /issue_statuses.json and populate caches.

    Called at startup with retries. If Redmine is not ready, falls back to
    default mappings so the backend can still start.
    """
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(
                base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=5.0
            ) as c:
                r = await c.get("/issue_statuses.json")

            if r.status_code != 200:
                raise RuntimeError(f"GET issue_statuses failed: {r.status_code}")

            # Guard against empty response bodies (Redmine not ready yet).
            body = r.text.strip()
            if not body:
                raise ValueError("Empty response from Redmine")

            statuses = r.json().get("issue_statuses", [])
            if not statuses:
                raise ValueError("No issue statuses returned from Redmine")

            for s in statuses:
                sid = int(s["id"])
                name = s.get("name", "")
                normalized_name = name.strip().casefold()
                slug = s.get("slug", "").strip().casefold()
                _status_by_name[name] = sid
                _status_by_id[sid] = name

                for key, aliases in _ENGLISH_KEY_MATCHERS.items():
                    if slug in aliases or normalized_name in aliases:
                        _status_by_key[key] = sid
                        break
                else:
                    if slug and slug in _ENGLISH_KEY_MATCHERS:
                        _status_by_key[slug] = sid

            logger.info(
                "Loaded %d statuses from Redmine (attempt %d)",
                len(_status_by_id),
                attempt,
            )
            return  # Success!

        except (httpx.HTTPError, RuntimeError, ValueError, KeyError) as exc:
            logger.warning(
                "Failed to fetch statuses (attempt %d/3): %s", attempt, exc
            )

    # All retries failed -- use defaults.
    logger.warning("Using default fallback status mapping")
    _status_by_key.update(_DEFAULT_KEY_FALLBACK)
    for key, sid in _DEFAULT_KEY_FALLBACK.items():
        _status_by_id[sid] = key


def _client(api_key: str) -> httpx.AsyncClient:
    headers = {"X-Redmine-API-Key": api_key, "Content-Type": "application/json"}
    return httpx.AsyncClient(base_url=REDMINE_BASE_URL, headers=headers, timeout=10.0)


def get_session_store() -> SessionStore:
    return session_store


async def require_session(
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    store: SessionStore = Depends(get_session_store),
) -> SessionData:
    if not session_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return session


# ── Helpers ─────────────────────────────────────────────────────────

def _redmine_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _issue_custom_fields(i: Dict[str, Any], include_support_only: bool) -> Dict[str, Any]:
    values_by_name = {
        field.get("name"): field.get("value")
        for field in i.get("custom_fields", [])
        if isinstance(field, dict)
    }
    result: Dict[str, Any] = {}
    for key, definition in CUSTOM_FIELD_DEFINITIONS.items():
        if definition["support_only"] and not include_support_only:
            continue
        value = values_by_name.get(definition["name"], "0" if definition["boolean"] else "")
        result[key] = _redmine_bool(value) if definition["boolean"] else str(value or "")
    return result


def _issue_to_dict(i: Dict[str, Any], include_support_only: bool = True) -> Dict[str, Any]:
    """Extract common fields from a Redmine issue dict."""
    assigned_to = i.get("assigned_to")
    result = {
        "id": i["id"],
        "subject": i.get("subject", ""),
        "description": i.get("description", ""),
        "status": i["status"]["name"],
        "priority": int(i["priority"]["id"]),
        "priority_name": i["priority"].get("name", ""),
        "assignee": (
            {
                "id": int(assigned_to["id"]),
                "name": assigned_to.get("name", ""),
            }
            if assigned_to
            else None
        ),
        "created_on": i.get("created_on", ""),
        "updated_on": i.get("updated_on", ""),
    }
    result.update(_issue_custom_fields(i, include_support_only))
    return result


def _latest_support_responder(
    issue: Dict[str, Any], support_user_ids: set[int]
) -> Optional[Dict[str, Any]]:
    """Return the support user who most recently acted in the issue journal."""
    support_journals = []
    for journal in issue.get("journals", []):
        user = journal.get("user")
        if not isinstance(user, dict) or "id" not in user:
            continue
        try:
            user_id = int(user["id"])
        except (TypeError, ValueError):
            continue
        if user_id in support_user_ids:
            support_journals.append((journal.get("created_on", ""), user_id, user))

    if not support_journals:
        return None
    _, user_id, user = max(support_journals, key=lambda entry: entry[0])
    return {"id": user_id, "name": user.get("name", "")}


def _next_priority_id(
    current_priority_id: int, priorities: List[Dict[str, Any]]
) -> int:
    """Return the next Redmine priority by enumeration order, capped at the top."""
    ids = [int(priority["id"]) for priority in priorities]
    try:
        current_index = ids.index(int(current_priority_id))
    except ValueError:
        raise HTTPException(status_code=503, detail="現在の優先度設定を解決できません") from None
    return ids[min(current_index + 1, len(ids) - 1)]


async def _issue_priorities(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    response = await client.get("/enumerations/issue_priorities.json")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="優先度設定を取得できません")
    priorities = response.json().get("issue_priorities", [])
    if not priorities:
        raise HTTPException(status_code=503, detail="優先度設定がありません")
    try:
        return [
            {
                **priority,
                "id": int(priority["id"]),
                "name": str(priority.get("name", "")),
            }
            for priority in priorities
        ]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=503, detail="優先度設定の形式が不正です"
        ) from None


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
    clean = field.removesuffix("_id")
    return _FIELD_NAME_MAP.get(clean, field)


def _journals_to_audit(
    journals: List[Dict[str, Any]],
    user_names: Optional[Dict[int, str]] = None,
    status_names: Optional[Dict[int, str]] = None,
    custom_fields: Optional[Dict[int, Dict[str, Any]]] = None,
    priority_names: Optional[Dict[int, str]] = None,
) -> List[Dict[str, Any]]:
    """Convert Redmine journals to audit log entries.

    Each journal entry becomes a dict with:
      type  : "comment" | "change" | "both"
      author: user name
      created_on: timestamp
      comment: text (if any)
      changes: list of field change dicts (if any)
    """
    entries: List[Dict[str, Any]] = []
    user_names = user_names or {}
    status_names = status_names or {}
    custom_fields = custom_fields or {}
    priority_names = priority_names or {}

    def custom_field_definition(detail: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if detail.get("property") != "cf":
            return None
        try:
            return custom_fields.get(int(detail.get("name", "")))
        except (TypeError, ValueError):
            return None

    def change_dict(detail: Dict[str, Any]) -> Dict[str, Any]:
        # Redmine 6 uses `name`; older/test payloads may use `prop_key`.
        field = detail.get("name") or detail.get("prop_key", "")
        old_value = detail.get("old_value")
        new_value = detail.get("new_value")
        custom_definition = custom_field_definition(detail)
        if custom_definition:
            field = custom_definition["key"]
            if custom_definition["boolean"]:
                old_value = "はい" if _redmine_bool(old_value) else "いいえ"
                new_value = "はい" if _redmine_bool(new_value) else "いいえ"
        elif field in ("assigned_to", "assigned_to_id"):
            old_value = _user_name_for_audit(old_value, user_names)
            new_value = _user_name_for_audit(new_value, user_names)
        elif field in ("status", "status_id"):
            old_value = _status_name_for_audit(old_value, status_names)
            new_value = _status_name_for_audit(new_value, status_names)
        elif field in ("priority", "priority_id"):
            old_value = _priority_name_for_audit(old_value, priority_names)
            new_value = _priority_name_for_audit(new_value, priority_names)
        return {
            "field": field,
            "display_field": (
                custom_definition["label"]
                if custom_definition
                else _field_display_name(field)
            ),
            "old_value": old_value,
            "new_value": new_value,
        }

    for j in journals:
        body = j.get("notes", "")
        details = [
            detail
            for detail in j.get("details", [])
            if not (
                (definition := custom_field_definition(detail))
                and definition.get("hidden")
            )
        ]
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
            entry["changes"] = [change_dict(d) for d in details]
        elif has_comment:
            entry["type"] = "comment"
            entry["comment"] = body
            entry["changes"] = []
        elif has_changes:
            entry["type"] = "change"
            entry["changes"] = [change_dict(d) for d in details]
        else:
            # Journal with no notes and no details -- skip it.
            continue

        entries.append(entry)
    return entries


def _user_name_for_audit(
    value: Any,
    user_names: Dict[int, str],
) -> Any:
    """Replace a Redmine user ID with its display name when available."""
    if value in (None, ""):
        return value
    try:
        return user_names.get(int(value), value)
    except (TypeError, ValueError):
        return value


def _status_name_for_audit(
    value: Any,
    status_names: Dict[int, str],
) -> Any:
    """Replace a Redmine status ID with its display name when available."""
    if value in (None, ""):
        return value
    try:
        return status_names.get(int(value), value)
    except (TypeError, ValueError):
        return value


def _priority_name_for_audit(
    value: Any,
    priority_names: Dict[int, str],
) -> Any:
    """Replace a Redmine priority ID with its display name when available."""
    if value in (None, ""):
        return value
    try:
        return priority_names.get(int(value), value)
    except (TypeError, ValueError):
        return value


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


async def _support_user_ids() -> set[int]:
    """Return project members who have the support role."""
    support_ids: set[int] = set()
    offset = 0
    limit = 100

    async with httpx.AsyncClient(
        base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0
    ) as client:
        while True:
            response = await client.get(
                f"/projects/{REDMINE_PROJECT_ID}/memberships.json",
                params={"limit": limit, "offset": offset},
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"GET project memberships failed: {response.status_code}"
                )

            body = response.json()
            memberships = body.get("memberships", [])
            for membership in memberships:
                user = membership.get("user")
                roles = membership.get("roles", [])
                if user and any(
                    _ROLE_BY_REDMINE_NAME.get(role.get("name")) == ROLE_SUPPORT
                    for role in roles
                ):
                    support_ids.add(int(user["id"]))

            total_count = int(body.get("total_count", len(memberships)))
            offset += len(memberships)
            if not memberships or offset >= total_count:
                break

    return support_ids


async def _user_roles(user_id: int) -> set[str]:
    """Return canonical portal roles for a Redmine project member."""
    offset = 0
    limit = 100
    async with httpx.AsyncClient(
        base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0
    ) as client:
        while True:
            response = await client.get(
                f"/projects/{REDMINE_PROJECT_ID}/memberships.json",
                params={"limit": limit, "offset": offset},
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"GET project memberships failed: {response.status_code}"
                )
            body = response.json()
            memberships = body.get("memberships", [])
            for membership in memberships:
                user = membership.get("user")
                if user and int(user["id"]) == user_id:
                    return {
                        portal_role
                        for role in membership.get("roles", [])
                        if (
                            portal_role := _ROLE_BY_REDMINE_NAME.get(
                                role.get("name", "")
                            )
                        )
                    }
            offset += len(memberships)
            if not memberships or offset >= int(
                body.get("total_count", len(memberships))
            ):
                break
    return set()


async def _session_user(session: SessionData) -> Dict[str, Any]:
    """Build the public session user payload without exposing credentials."""
    if session.is_admin:
        roles = {ROLE_ADMIN}
    else:
        try:
            roles = await _user_roles(session.redmine_user_id)
        except (httpx.HTTPError, RuntimeError, ValueError, KeyError):
            roles = set()
    return {
        "id": session.redmine_user_id,
        "username": session.username,
        "name": session.name,
        "roles": sorted(roles),
    }


async def _required_user_roles(user_id: int) -> set[str]:
    """Load portal roles or fail closed when Redmine cannot verify them."""
    try:
        return await _user_roles(user_id)
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError):
        raise HTTPException(
            status_code=503,
            detail="ユーザーのロールを確認できませんでした",
        ) from None


async def _faq_roles(session: SessionData) -> set[str]:
    if session.is_admin:
        return {ROLE_ADMIN}
    return await _required_user_roles(session.redmine_user_id)


async def _require_faq_read(session: SessionData) -> set[str]:
    roles = await _faq_roles(session)
    if not roles.intersection({ROLE_SALES, ROLE_SUPPORT, ROLE_ADMIN}):
        raise HTTPException(status_code=403, detail="FAQの閲覧権限がありません")
    return roles


async def _require_faq_write(session: SessionData) -> set[str]:
    roles = await _faq_roles(session)
    if not roles.intersection({ROLE_SUPPORT, ROLE_ADMIN}):
        raise HTTPException(status_code=403, detail="FAQの編集権限がありません")
    return roles


async def _require_support_role(user_id: int) -> None:
    """Require the support role for responder-only operations."""
    if ROLE_SUPPORT not in await _required_user_roles(user_id):
        raise HTTPException(status_code=403, detail="サポートロールが必要です")


async def _project_user_names() -> Dict[int, str]:
    """Return a user ID to display name map for the current project."""
    names: Dict[int, str] = {}
    offset = 0
    limit = 100

    async with httpx.AsyncClient(
        base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0
    ) as client:
        while True:
            response = await client.get(
                f"/projects/{REDMINE_PROJECT_ID}/memberships.json",
                params={"limit": limit, "offset": offset},
            )
            if response.status_code != 200:
                break
            body = response.json()
            memberships = body.get("memberships", [])
            for membership in memberships:
                user = membership.get("user")
                if user:
                    names[int(user["id"])] = user.get("name", "")
            total_count = int(body.get("total_count", len(memberships)))
            offset += len(memberships)
            if not memberships or offset >= total_count:
                break

    return names


async def _custom_field_ids() -> Dict[str, int]:
    """Resolve configured issue custom fields by name using the service API key."""
    async with httpx.AsyncClient(
        base_url=REDMINE_BASE_URL, headers=HEADERS, timeout=10.0
    ) as client:
        response = await client.get("/custom_fields.json")
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="カスタムフィールド設定を取得できませんでした")
    fields = response.json().get("custom_fields", [])
    ids_by_name = {
        field.get("name"): int(field["id"])
        for field in fields
        if field.get("id") is not None
    }
    missing = [
        definition["name"]
        for definition in CUSTOM_FIELD_DEFINITIONS.values()
        if definition["name"] not in ids_by_name
    ]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"カスタムフィールドが設定されていません: {', '.join(missing)}",
        )
    return {
        key: ids_by_name[definition["name"]]
        for key, definition in CUSTOM_FIELD_DEFINITIONS.items()
    }


def _custom_fields_payload(values: Dict[str, Any], ids: Dict[str, int]) -> List[Dict[str, Any]]:
    payload = []
    for key, value in values.items():
        definition = CUSTOM_FIELD_DEFINITIONS[key]
        redmine_value = ("1" if value else "0") if definition["boolean"] else str(value or "")
        payload.append({"id": ids[key], "value": redmine_value})
    return payload


def _custom_field_audit_metadata(
    ids: Dict[str, int], include_support_only: bool
) -> Dict[int, Dict[str, Any]]:
    return {
        field_id: {
            "key": key,
            "label": definition["label"],
            "boolean": definition["boolean"],
            "hidden": definition["support_only"] and not include_support_only,
        }
        for key, field_id in ids.items()
        for definition in [CUSTOM_FIELD_DEFINITIONS[key]]
    }


def _faq_text(question: str, answer: str) -> str:
    return f"Q: {question}\n\nA:\n{answer}"


def _parse_faq_page(page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = str(page.get("title", ""))
    if not title.startswith(FAQ_PAGE_PREFIX):
        return None
    match = FAQ_TEXT_PATTERN.match(str(page.get("text", "")))
    if match is None:
        logger.warning("Ignoring malformed FAQ wiki page %s", title)
        return None
    author = page.get("author")
    return {
        "id": title.removeprefix(FAQ_PAGE_PREFIX),
        "question": match.group("question").strip(),
        "answer": match.group("answer").strip(),
        "version": int(page.get("version", 1)),
        "author": author.get("name", "") if isinstance(author, dict) else "",
        "created_on": page.get("created_on", ""),
        "updated_on": page.get("updated_on", ""),
    }


def _faq_page_title(faq_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", faq_id):
        raise HTTPException(status_code=404, detail="FAQが見つかりません")
    return f"{FAQ_PAGE_PREFIX}{faq_id}"


def _faq_page_path(title: str) -> str:
    return f"/projects/{quote(REDMINE_PROJECT_ID, safe='')}/wiki/{quote(title, safe='')}.json"


def _validated_faq_fields(question: str, answer: str) -> tuple[str, str]:
    normalized_question = question.strip()
    normalized_answer = answer.strip()
    if not normalized_question or not normalized_answer:
        raise HTTPException(status_code=422, detail="質問と回答は必須です")
    if "\n" in normalized_question or "\r" in normalized_question:
        raise HTTPException(status_code=422, detail="質問に改行は使用できません")
    if len(normalized_question) > 200:
        raise HTTPException(status_code=422, detail="質問は200文字以内で入力してください")
    return normalized_question, normalized_answer


async def _redmine_faq_page(
    client: httpx.AsyncClient, title: str
) -> Optional[Dict[str, Any]]:
    response = await client.get(_faq_page_path(title))
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="FAQを取得できませんでした")
    return response.json().get("wiki_page")


# ── Endpoints ───────────────────────────────────────────────────────

class CreateTicketRequest(BaseModel):
    subject: str
    description: str
    priority: Optional[int] = None
    # Backward-compatible input only. Creation always uses the inquiry tracker.
    tracker_id: Optional[int] = None
    customer_id: str = ""
    report_required: bool = False
    report_delivered: bool = False
    customer_visit_required: bool = False
    schedule_assigned: bool = False


class UpdateCustomFieldsRequest(BaseModel):
    customer_id: Optional[str] = None
    report_required: Optional[bool] = None
    report_delivered: Optional[bool] = None
    customer_visit_required: Optional[bool] = None
    schedule_assigned: Optional[bool] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class FaqWriteRequest(BaseModel):
    question: str
    answer: str
    version: Optional[int] = None


@app.get("/faqs")
async def list_faqs(
    q: str = "",
    limit: int = 20,
    offset: int = 0,
    session: SessionData = Depends(require_session),
):
    await _require_faq_read(session)
    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail="ページネーション指定が不正です")

    async with _client(session.redmine_api_key) as client:
        response = await client.get(
            f"/projects/{quote(REDMINE_PROJECT_ID, safe='')}/wiki/index.json"
        )
        if response.status_code != 200:
            raise HTTPException(status_code=503, detail="FAQ一覧を取得できませんでした")
        titles = [
            str(page.get("title", ""))
            for page in response.json().get("wiki_pages", [])
            if str(page.get("title", "")).startswith(FAQ_PAGE_PREFIX)
        ]
        pages = await asyncio.gather(
            *(_redmine_faq_page(client, title) for title in titles)
        )

    faqs = [faq for page in pages if page and (faq := _parse_faq_page(page))]
    query = q.strip().casefold()
    if query:
        faqs = [
            faq
            for faq in faqs
            if query in faq["question"].casefold() or query in faq["answer"].casefold()
        ]
    faqs.sort(key=lambda faq: (faq["updated_on"], faq["question"]), reverse=True)
    total_count = len(faqs)
    items = faqs[offset : offset + limit]
    return {
        "faqs": items,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total_count": total_count,
            "has_more": offset + len(items) < total_count,
        },
    }


@app.post("/faqs", status_code=201)
async def create_faq(
    faq_data: FaqWriteRequest,
    session: SessionData = Depends(require_session),
):
    await _require_faq_write(session)
    question, answer = _validated_faq_fields(faq_data.question, faq_data.answer)
    title = f"{FAQ_PAGE_PREFIX}{uuid.uuid4().hex}"
    async with _client(session.redmine_api_key) as client:
        response = await client.put(
            _faq_page_path(title),
            json={"wiki_page": {"text": _faq_text(question, answer)}},
        )
        if response.status_code not in (201, 204):
            return JSONResponse(status_code=response.status_code, content={"detail": response.text})
        page = await _redmine_faq_page(client, title)
    if page is None or (faq := _parse_faq_page(page)) is None:
        raise HTTPException(status_code=503, detail="作成したFAQを取得できませんでした")
    logger.info("Created FAQ %s", faq["id"])
    return faq


@app.get("/faqs/{faq_id}")
async def get_faq(
    faq_id: str,
    session: SessionData = Depends(require_session),
):
    await _require_faq_read(session)
    title = _faq_page_title(faq_id)
    async with _client(session.redmine_api_key) as client:
        page = await _redmine_faq_page(client, title)
    if page is None or (faq := _parse_faq_page(page)) is None:
        raise HTTPException(status_code=404, detail="FAQが見つかりません")
    return faq


@app.put("/faqs/{faq_id}")
async def update_faq(
    faq_id: str,
    faq_data: FaqWriteRequest,
    session: SessionData = Depends(require_session),
):
    await _require_faq_write(session)
    question, answer = _validated_faq_fields(faq_data.question, faq_data.answer)
    if faq_data.version is None or faq_data.version < 1:
        raise HTTPException(status_code=422, detail="FAQのバージョンが必要です")
    title = _faq_page_title(faq_id)
    async with _client(session.redmine_api_key) as client:
        response = await client.put(
            _faq_page_path(title),
            json={
                "wiki_page": {
                    "text": _faq_text(question, answer),
                    "version": faq_data.version,
                }
            },
        )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="FAQが見つかりません")
        if response.status_code == 409:
            raise HTTPException(status_code=409, detail="FAQが他のユーザーに更新されています")
        if response.status_code != 204:
            return JSONResponse(status_code=response.status_code, content={"detail": response.text})
        page = await _redmine_faq_page(client, title)
    if page is None or (faq := _parse_faq_page(page)) is None:
        raise HTTPException(status_code=503, detail="更新したFAQを取得できませんでした")
    logger.info("Updated FAQ %s", faq_id)
    return faq


@app.delete("/faqs/{faq_id}")
async def delete_faq(
    faq_id: str,
    session: SessionData = Depends(require_session),
):
    await _require_faq_write(session)
    title = _faq_page_title(faq_id)
    async with _client(session.redmine_api_key) as client:
        response = await client.delete(_faq_page_path(title))
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="FAQが見つかりません")
    if response.status_code != 204:
        return JSONResponse(status_code=response.status_code, content={"detail": response.text})
    logger.info("Deleted FAQ %s", faq_id)
    return {"detail": "FAQを削除しました"}


@app.get("/priority/options")
async def priority_options(session: SessionData = Depends(require_session)):
    async with _client(session.redmine_api_key) as client:
        priorities = await _issue_priorities(client)
    return [
        {
            "id": int(priority["id"]),
            "label": priority.get("name", ""),
            "is_default": bool(priority.get("is_default", False)),
        }
        for priority in priorities
    ]


@app.post("/auth/login")
async def login(
    credentials: LoginRequest,
    response: Response,
    store: SessionStore = Depends(get_session_store),
):
    username = credentials.username.strip()
    if not username or not credentials.password:
        raise HTTPException(status_code=422, detail="Username and password are required")

    try:
        session = await authenticate_with_redmine(
            REDMINE_BASE_URL, username, credentials.password
        )
    except (httpx.HTTPError, RuntimeError, KeyError, ValueError):
        # Do not expose whether the account exists or why Redmine rejected it.
        raise HTTPException(status_code=401, detail="Invalid username or password") from None
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_id = await store.create(session)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {
        "authenticated": True,
        "user": await _session_user(session),
    }


@app.get("/auth/session")
async def current_session(session: SessionData = Depends(require_session)):
    return {
        "authenticated": True,
        "user": await _session_user(session),
    }


@app.post("/auth/logout")
async def logout(
    response: Response,
    session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    store: SessionStore = Depends(get_session_store),
):
    if session_id:
        await store.delete(session_id)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="lax",
    )
    return {"detail": "Logged out"}

@app.post("/tickets")
async def create_ticket(
    ticket_data: CreateTicketRequest,
    session: SessionData = Depends(require_session),
):
    with tracer.start_as_current_span("create_ticket") as span:
        subject = ticket_data.subject.strip()
        description = ticket_data.description.strip()
        priority = ticket_data.priority
        span.set_attribute("request.subject", subject)

        if not subject or not description:
            return JSONResponse(
                status_code=422,
                content={"detail": "subject and description are required"},
            )

        roles = await _required_user_roles(session.redmine_user_id)
        field_values = {
            "customer_id": ticket_data.customer_id.strip(),
            "report_required": ticket_data.report_required,
            "report_delivered": ticket_data.report_delivered if ROLE_SUPPORT in roles else False,
            "customer_visit_required": ticket_data.customer_visit_required,
            "schedule_assigned": ticket_data.schedule_assigned if ROLE_SUPPORT in roles else False,
        }
        field_ids = await _custom_field_ids()
        payload = {
            "issue": {
                "project_id": int(REDMINE_PROJECT_ID),
                "tracker_id": int(REDMINE_TRACKER_ID),
                "subject": subject,
                "description": description,
                "custom_fields": _custom_fields_payload(field_values, field_ids),
            }
        }
        if priority is not None:
            payload["issue"]["priority_id"] = priority
        async with _client(session.redmine_api_key) as c:
            if (
                priority is not None
                and any(
                    getattr(ticket_data, field) for field in PRIORITY_ESCALATION_FIELDS
                )
            ):
                payload["issue"]["priority_id"] = _next_priority_id(
                    priority, await _issue_priorities(c)
                )
            r = await c.post("/issues.json", json=payload)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 201:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            issue = r.json()["issue"]
            result = _issue_to_dict(issue, include_support_only=ROLE_SUPPORT in roles)
            logger.info("Created ticket %s", result["id"])
            return result


@app.get("/tickets")
async def list_tickets(
    request: Request, session: SessionData = Depends(require_session)
):
    with tracer.start_as_current_span("list_tickets") as span:
        qs = dict(request.query_params)
        status_key = qs.get("status", "")
        responder_view = qs.get("view") == "responder"
        roles = await _required_user_roles(session.redmine_user_id)
        is_support = ROLE_SUPPORT in roles
        is_sales = ROLE_SALES in roles
        if responder_view and not is_support:
            raise HTTPException(status_code=403, detail="サポートロールが必要です")
        if not is_support and not is_sales:
            raise HTTPException(status_code=403, detail="利用可能なロールがありません")
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

        # Redmine defaults an omitted status_id to open issues. Request every
        # status explicitly so the portal's 「すべて」 cache also contains
        # closed tickets for local filtering.
        params: Dict[str, Any] = {
            "project_id": REDMINE_PROJECT_ID,
            "status_id": "*",
        }

        # Translate frontend's English status key → Redmine status_id for filtering.
        if responder_view:
            # Redmine's special "open" value includes every non-closed status,
            # including newly created tickets.
            params["status_id"] = "open"
        elif status_key:
            sid = _resolve_status_id(status_key)
            if sid is not None:
                params["status_id"] = sid
            else:
                logger.warning("Unknown status filter %r", status_key)

        # Responder filtering happens after fetching because Redmine cannot
        # filter assignees by project role.
        filters_locally = responder_view or (is_sales and not is_support)
        params["limit"] = 1000 if filters_locally else limit
        params["offset"] = 0 if filters_locally else offset

        async with _client(session.redmine_api_key) as c:
            r = await c.get("/issues.json", params=params)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 200:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})

            # Redmine normally honors limit, but keep our API contract even if
            # an upstream proxy/mock returns more rows than requested.
            issues = r.json()["issues"]
            if responder_view:
                responder_statuses = {
                    "対応待ち",
                    "対応中",
                    "クローズ待ち",
                    # Backward compatibility while an existing environment is
                    # being migrated by the bootstrap.
                    "New",
                    "In Progress",
                    "Rejected",
                }
                try:
                    support_ids = await _support_user_ids()
                except (httpx.HTTPError, RuntimeError, ValueError, KeyError):
                    support_ids = {session.redmine_user_id}
                issues = [
                    issue
                    for issue in issues
                    if issue.get("status", {}).get("name") in responder_statuses
                    and (
                        not issue.get("assigned_to")
                    or int(issue["assigned_to"]["id"]) in support_ids
                    )
                ]
                total_count = len(issues)
                issues = issues[offset : offset + limit]
                detail_responses = await asyncio.gather(
                    *(
                        c.get(
                            f"/issues/{issue['id']}.json",
                            params={"include": "journals"},
                        )
                        for issue in issues
                    ),
                    return_exceptions=True,
                )
                latest_responders: Dict[int, Optional[Dict[str, Any]]] = {}
                for issue, detail_response in zip(issues, detail_responses):
                    latest_responders[int(issue["id"])] = (
                        _latest_support_responder(
                            detail_response.json().get("issue", {}), support_ids
                        )
                        if isinstance(detail_response, httpx.Response)
                        and detail_response.status_code == 200
                        else None
                    )
            elif is_sales and not is_support:
                issues = [
                    issue
                    for issue in issues
                    if (
                        int(issue.get("author", {}).get("id", -1))
                        == session.redmine_user_id
                        or int(issue.get("assigned_to", {}).get("id", -1))
                        == session.redmine_user_id
                    )
                ]
                total_count = len(issues)
                issues = issues[offset : offset + limit]
            else:
                issues = issues[:limit]
                total_count = r.json().get("total_count", len(issues))
            result = [_issue_to_dict(i, include_support_only=is_support) for i in issues]
            if responder_view:
                for ticket in result:
                    ticket["latest_support_responder"] = latest_responders.get(ticket["id"])
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
async def get_ticket(ticket_id: int, session: SessionData = Depends(require_session)):
    with tracer.start_as_current_span("get_ticket") as span:
        span.set_attribute("ticket.id", ticket_id)
        async with _client(session.redmine_api_key) as c:
            # include=journals fetches comment history
            r = await c.get(f"/issues/{ticket_id}.json", params={"include": "journals"})
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code != 200:
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            i = r.json()["issue"]
            roles = await _required_user_roles(session.redmine_user_id)
            is_support = ROLE_SUPPORT in roles
            data = _issue_to_dict(i, include_support_only=is_support)
            try:
                user_names = await _project_user_names()
            except (httpx.HTTPError, ValueError, KeyError):
                user_names = {}
            user_names[session.redmine_user_id] = session.name
            assigned_to = i.get("assigned_to")
            if assigned_to:
                user_names[int(assigned_to["id"])] = assigned_to.get("name", "")
            try:
                priority_names = {
                    int(priority["id"]): priority["name"]
                    for priority in await _issue_priorities(c)
                }
            except HTTPException:
                priority = i.get("priority") or {}
                priority_names = (
                    {int(priority["id"]): priority.get("name", "")}
                    if priority.get("id") is not None
                    else {}
                )
            # Full audit log with comments + field changes.
            data["audit_log"] = _journals_to_audit(
                i.get("journals", []),
                user_names,
                _status_by_id,
                _custom_field_audit_metadata(await _custom_field_ids(), is_support),
                priority_names,
            )
            # Also provide backward-compatible notes list.
            data["notes"] = _journals_to_notes(i.get("journals", []))
            return data


@app.patch("/tickets/{ticket_id}/custom-fields")
async def update_custom_fields(
    ticket_id: int,
    field_data: UpdateCustomFieldsRequest,
    session: SessionData = Depends(require_session),
):
    values = field_data.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=422, detail="更新するカスタムフィールドがありません")

    roles = await _required_user_roles(session.redmine_user_id)
    if ROLE_SUPPORT not in roles and any(
        CUSTOM_FIELD_DEFINITIONS[key]["support_only"] for key in values
    ):
        raise HTTPException(status_code=403, detail="サポートロールが必要です")
    if "customer_id" in values:
        values["customer_id"] = (values["customer_id"] or "").strip()

    field_ids = await _custom_field_ids()
    payload = {"issue": {"custom_fields": _custom_fields_payload(values, field_ids)}}
    async with _client(session.redmine_api_key) as client:
        escalates_priority = any(
            values.get(key) is True for key in PRIORITY_ESCALATION_FIELDS
        )
        reassigns_to_author = any(
            values.get(key) is True for key in AUTHOR_REASSIGNMENT_FIELDS
        )
        current_issue = None
        if escalates_priority or reassigns_to_author:
            current_response = await client.get(f"/issues/{ticket_id}.json")
            if current_response.status_code != 200:
                return JSONResponse(
                    status_code=current_response.status_code,
                    content={"detail": current_response.text},
                )
            current_issue = current_response.json()["issue"]

        if escalates_priority and current_issue is not None:
            waiting_status_id = _resolve_status_id("open")
            if waiting_status_id is None:
                raise HTTPException(
                    status_code=503,
                    detail="対応待ちステータスが設定されていません",
                )
            payload["issue"]["status_id"] = waiting_status_id
            payload["issue"]["assigned_to_id"] = ""

            current_fields = _issue_custom_fields(current_issue, include_support_only=False)
            newly_checked = any(
                values.get(key) is True and not current_fields.get(key, False)
                for key in PRIORITY_ESCALATION_FIELDS
            )
            if newly_checked:
                current_priority = int(current_issue["priority"]["id"])
                payload["issue"]["priority_id"] = _next_priority_id(
                    current_priority, await _issue_priorities(client)
                )

        if reassigns_to_author and current_issue is not None:
            author = current_issue.get("author")
            if not author or author.get("id") is None:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "チケットの起票者を取得できませんでした"},
                )
            completed_status_id = _resolve_status_id("answered")
            if completed_status_id is None:
                raise HTTPException(
                    status_code=503,
                    detail="対応済ステータスが設定されていません",
                )
            payload["issue"]["status_id"] = completed_status_id
            payload["issue"]["assigned_to_id"] = int(author["id"])

        response = await client.put(f"/issues/{ticket_id}.json", json=payload)
    if response.status_code not in (200, 204):
        return JSONResponse(status_code=response.status_code, content={"detail": response.text})
    return {"detail": "Custom fields updated"}


class AddCommentRequest(BaseModel):
    body: str

@app.post("/tickets/{ticket_id}/comments")
async def add_comment(
    ticket_id: int,
    comment_data: AddCommentRequest,
    session: SessionData = Depends(require_session),
):
    with tracer.start_as_current_span("add_comment") as span:
        span.set_attribute("ticket.id", ticket_id)
        body = comment_data.body.strip()
        if not body:
            return JSONResponse(status_code=422, content={"detail": "body is required"})
        payload = {"issue": {"notes": body}}
        async with _client(session.redmine_api_key) as client:
            r = await client.put(f"/issues/{ticket_id}.json", json=payload)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code not in (200, 204):
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            return {"detail": "Comment added"}


@app.post("/tickets/{ticket_id}/answer")
async def answer_ticket(
    ticket_id: int,
    comment_data: AddCommentRequest,
    session: SessionData = Depends(require_session),
):
    """Add an answer and return the ticket to the user who created it."""
    with tracer.start_as_current_span("answer_ticket") as span:
        span.set_attribute("ticket.id", ticket_id)
        body = comment_data.body.strip()
        if not body:
            return JSONResponse(status_code=422, content={"detail": "body is required"})

        await _require_support_role(session.redmine_user_id)

        answered_status_id = _resolve_status_id("answered")
        if answered_status_id is None:
            raise HTTPException(
                status_code=503,
                detail="対応済ステータスが設定されていません",
            )

        async with _client(session.redmine_api_key) as client:
            issue_response = await client.get(f"/issues/{ticket_id}.json")
            span.set_attribute("redmine.get_status", issue_response.status_code)
            if issue_response.status_code != 200:
                return JSONResponse(
                    status_code=issue_response.status_code,
                    content={"detail": issue_response.text},
                )

            author = issue_response.json()["issue"].get("author")
            if not author or author.get("id") is None:
                return JSONResponse(
                    status_code=409,
                    content={"detail": "チケットの起票者を取得できませんでした"},
                )

            payload = {
                "issue": {
                    "notes": body,
                    "assigned_to_id": int(author["id"]),
                    "status_id": answered_status_id,
                }
            }
            response = await client.put(f"/issues/{ticket_id}.json", json=payload)

        span.set_attribute("redmine.status", response.status_code)
        if response.status_code not in (200, 204):
            return JSONResponse(
                status_code=response.status_code,
                content={"detail": response.text},
            )
        return {"detail": "Answer added; ticket assigned to author and marked answered"}


class UpdateStatusRequest(BaseModel):
    status_id: int


class UpdatePriorityRequest(BaseModel):
    priority_id: int


@app.patch("/tickets/{ticket_id}/assignee")
async def claim_ticket(
    ticket_id: int,
    session: SessionData = Depends(require_session),
):
    """Assign a ticket to the currently signed-in Redmine user."""
    with tracer.start_as_current_span("claim_ticket") as span:
        await _require_support_role(session.redmine_user_id)
        span.set_attribute("ticket.id", ticket_id)
        span.set_attribute("assignee.id", session.redmine_user_id)
        in_progress_id = _resolve_status_id("in_progress")
        if in_progress_id is None:
            raise HTTPException(
                status_code=503,
                detail="対応中ステータスが設定されていません",
            )
        payload = {
            "issue": {
                "assigned_to_id": session.redmine_user_id,
                "status_id": in_progress_id,
            }
        }
        async with _client(session.redmine_api_key) as client:
            response = await client.put(
                f"/issues/{ticket_id}.json",
                json=payload,
            )
        span.set_attribute("redmine.status", response.status_code)
        if response.status_code not in (200, 204):
            return JSONResponse(
                status_code=response.status_code,
                content={"detail": response.text},
            )
        async with _client(session.redmine_api_key) as client:
            refreshed = await client.get(f"/issues/{ticket_id}.json")
        if refreshed.status_code != 200:
            return JSONResponse(
                status_code=refreshed.status_code,
                content={"detail": refreshed.text},
            )
        issue = refreshed.json()["issue"]
        assignee = issue.get("assigned_to")
        if (
            int(issue["status"]["id"]) != in_progress_id
            or not assignee
            or int(assignee["id"]) != session.redmine_user_id
        ):
            return JSONResponse(
                status_code=409,
                content={
                    "detail": "担当者または対応中ステータスを反映できませんでした"
                },
            )
        return {"detail": "Assignee and status updated"}


@app.patch("/tickets/{ticket_id}/status")
async def update_status(
    ticket_id: int,
    status_data: UpdateStatusRequest,
    session: SessionData = Depends(require_session),
):
    with tracer.start_as_current_span("update_status") as span:
        span.set_attribute("ticket.id", ticket_id)
        status_value = status_data.status_id
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

        if _status_by_id and sid not in _status_by_id:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Unknown status ID: {sid}"},
            )

        span.set_attribute("new.status_id", sid)
        payload = {"issue": {"status_id": sid}}
        clears_assignee = sid == _resolve_status_id("open")
        if clears_assignee:
            # A follow-up question returns the ticket to 対応待ち and the
            # shared support queue so another support user can claim it.
            # Redmine ignores JSON null for this field; an empty string is its
            # REST representation for "unassigned".
            payload["issue"]["assigned_to_id"] = ""
        async with _client(session.redmine_api_key) as client:
            r = await client.put(f"/issues/{ticket_id}.json", json=payload)
            span.set_attribute("redmine.status", r.status_code)
            if r.status_code not in (200, 204):
                return JSONResponse(status_code=r.status_code, content={"detail": r.text})
            refreshed = await client.get(f"/issues/{ticket_id}.json")
            if refreshed.status_code != 200:
                return JSONResponse(
                    status_code=refreshed.status_code,
                    content={"detail": refreshed.text},
                )
            actual_status_id = int(refreshed.json()["issue"]["status"]["id"])
            if actual_status_id != sid:
                return JSONResponse(
                    status_code=409,
                    content={
                        "detail": (
                            "このステータスへの変更は現在のワークフローでは"
                            "許可されていません"
                        )
                    },
                )
            if clears_assignee and refreshed.json()["issue"].get("assigned_to"):
                return JSONResponse(
                    status_code=409,
                    content={"detail": "担当者の解除を反映できませんでした"},
                )
            return {"detail": "Status updated"}


@app.patch("/tickets/{ticket_id}/priority")
async def update_priority(
    ticket_id: int,
    priority_data: UpdatePriorityRequest,
    session: SessionData = Depends(require_session),
):
    async with _client(session.redmine_api_key) as client:
        priorities = await _issue_priorities(client)
        valid_ids = {int(priority["id"]) for priority in priorities}
        priority_id = int(priority_data.priority_id)
        if priority_id not in valid_ids:
            raise HTTPException(status_code=400, detail="無効な優先度です")

        response = await client.put(
            f"/issues/{ticket_id}.json",
            json={"issue": {"priority_id": priority_id}},
        )
        if response.status_code not in (200, 204):
            return JSONResponse(
                status_code=response.status_code,
                content={"detail": response.text},
            )
        refreshed = await client.get(f"/issues/{ticket_id}.json")
        if refreshed.status_code != 200:
            return JSONResponse(
                status_code=refreshed.status_code,
                content={"detail": refreshed.text},
            )
        actual_priority_id = int(refreshed.json()["issue"]["priority"]["id"])
        if actual_priority_id != priority_id:
            return JSONResponse(
                status_code=409,
                content={"detail": "優先度を反映できませんでした"},
            )
    return {"detail": "Priority updated"}


@app.get("/status/options")
async def status_options(session: SessionData = Depends(require_session)):
    """Return all Redmine issue statuses for frontend dropdowns."""
    # Refresh with the signed-in user's API key. The startup cache may contain
    # only fallback values when Redmine was not ready yet.
    try:
        async with _client(session.redmine_api_key) as client:
            response = await client.get("/issue_statuses.json")
        if response.status_code == 200:
            statuses = response.json().get("issue_statuses", [])
            if statuses:
                refreshed_by_id: Dict[int, str] = {}
                refreshed_by_name: Dict[str, int] = {}
                for status in statuses:
                    sid = int(status["id"])
                    name = status.get("name", "")
                    refreshed_by_id[sid] = name
                    refreshed_by_name[name] = sid
                _status_by_id.clear()
                _status_by_id.update(refreshed_by_id)
                _status_by_name.clear()
                _status_by_name.update(refreshed_by_name)
    except (httpx.HTTPError, ValueError, KeyError):
        # Keep serving the last known cache if Redmine is temporarily down.
        pass

    result = []
    for sid, name in sorted(_status_by_id.items()):
        result.append({"id": sid, "label": name})
    return result


@app.get("/health")
async def health_check():
    """Return a minimal liveness response without exposing configuration."""
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Log unexpected failures while returning a stable public response."""
    logger.exception("Unhandled exception at %s", request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )
