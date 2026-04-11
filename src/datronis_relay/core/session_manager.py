from __future__ import annotations

import asyncio

from datronis_relay.core.ports import SessionStoreProtocol
from datronis_relay.domain.ids import SessionId, UserId, new_session_id


class SessionManager:
    """Owns per-user Claude session lifecycle.

    The concrete store is injected (in-memory for v0.1, SQLite for v0.2)
    so the manager itself never knows where state lives.

    `get_or_create` is check-then-act, so we hold a per-user lock across the
    read/write pair. Per-user granularity means concurrent users don't block
    each other. The lock map is itself guarded to avoid torn dictionary
    access on the event loop.
    """

    def __init__(self, store: SessionStoreProtocol) -> None:
        self._store = store
        self._user_locks: dict[UserId, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def get_or_create(self, user_id: UserId) -> SessionId:
        lock = await self._lock_for(user_id)
        async with lock:
            existing = await self._store.get(user_id)
            if existing is not None:
                return existing
            new_id = new_session_id()
            await self._store.set(user_id, new_id)
            return new_id

    async def reset(self, user_id: UserId) -> None:
        lock = await self._lock_for(user_id)
        async with lock:
            await self._store.drop(user_id)

    async def _lock_for(self, user_id: UserId) -> asyncio.Lock:
        async with self._locks_guard:
            lock = self._user_locks.get(user_id)
            if lock is None:
                lock = asyncio.Lock()
                self._user_locks[user_id] = lock
            return lock
