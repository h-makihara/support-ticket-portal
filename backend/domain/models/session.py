"""Authenticated-user domain model."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionData:
    """Server-side identity; the Redmine API key must never cross the API boundary."""

    redmine_user_id: int
    username: str
    name: str
    redmine_api_key: str
    created_at: str
    is_admin: bool = False
