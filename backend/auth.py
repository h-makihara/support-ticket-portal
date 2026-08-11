"""Backward-compatible imports for the relocated authentication adapter."""

from backend.domain.models.session import SessionData
from backend.infrastructure.session_store import (
    SESSION_TTL_SECONDS,
    SessionStore,
    authenticate_with_redmine,
)

__all__ = ["SESSION_TTL_SECONDS", "SessionData", "SessionStore", "authenticate_with_redmine"]
