import json

import pytest

from backend.auth import SESSION_TTL_SECONDS, SessionData, SessionStore


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.last_expiry = None

    async def set(self, key, value, ex):
        self.values[key] = value
        self.last_expiry = ex


@pytest.mark.asyncio
async def test_session_store_uses_fixed_six_hour_ttl():
    store = SessionStore.__new__(SessionStore)
    store.prefix = "session:"
    store.redis = FakeRedis()
    data = SessionData(1, "alice", "Alice", "secret-key", "2026-01-01T00:00:00Z")

    session_id = await store.create(data)

    assert len(session_id) >= 43
    assert store.redis.last_expiry == SESSION_TTL_SECONDS == 21_600
    saved = json.loads(store.redis.values[f"session:{session_id}"])
    assert saved["redmine_api_key"] == "secret-key"
