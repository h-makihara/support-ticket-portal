"""Redmine delegated authentication and Redis-backed sessions."""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
from redis.asyncio import Redis


SESSION_TTL_SECONDS = 21_600


@dataclass(frozen=True)
class SessionData:
    redmine_user_id: int
    username: str
    name: str
    redmine_api_key: str
    created_at: str


class SessionStore:
    def __init__(self, redis_url: str, prefix: str = "session:") -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)
        self.prefix = prefix

    def _key(self, session_id: str) -> str:
        return f"{self.prefix}{session_id}"

    async def create(self, data: SessionData) -> str:
        session_id = secrets.token_urlsafe(32)
        await self.redis.set(
            self._key(session_id),
            json.dumps(asdict(data)),
            ex=SESSION_TTL_SECONDS,
        )
        return session_id

    async def get(self, session_id: str) -> Optional[SessionData]:
        raw = await self.redis.get(self._key(session_id))
        if raw is None:
            return None
        try:
            return SessionData(**json.loads(raw))
        except (TypeError, ValueError, json.JSONDecodeError):
            await self.delete(session_id)
            return None

    async def delete(self, session_id: str) -> None:
        await self.redis.delete(self._key(session_id))

    async def close(self) -> None:
        await self.redis.aclose()


async def authenticate_with_redmine(
    base_url: str, username: str, password: str
) -> Optional[SessionData]:
    """Ask Redmine to authenticate and return the current user's API key."""
    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:
        response = await client.get(
            "/users/current.json",
            auth=httpx.BasicAuth(username, password),
            headers={"Accept": "application/json"},
        )

    if response.status_code in (401, 403):
        return None
    response.raise_for_status()
    user = response.json().get("user", {})
    api_key = user.get("api_key")
    if not api_key:
        raise RuntimeError("Redmine did not return an API key for the authenticated user")

    first_name = user.get("firstname", "")
    last_name = user.get("lastname", "")
    name = f"{first_name} {last_name}".strip() or user.get("login", username)
    return SessionData(
        redmine_user_id=int(user["id"]),
        username=user.get("login", username),
        name=name,
        redmine_api_key=api_key,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
