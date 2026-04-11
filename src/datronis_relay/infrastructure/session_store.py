from __future__ import annotations

import asyncio

from datronis_relay.core.ports import SessionStoreProtocol
from datronis_relay.domain.ids import SessionId, UserId


class InMemorySessionStore(SessionStoreProtocol):
    """Phase 1 store. State is lost on restart — Phase 2 swaps in SQLite."""

    def __init__(self) -> None:
        self._sessions: dict[UserId, SessionId] = {}
        self._lock = asyncio.Lock()

    async def get(self, user_id: UserId) -> SessionId | None:
        async with self._lock:
            return self._sessions.get(user_id)

    async def set(self, user_id: UserId, session_id: SessionId) -> None:
        async with self._lock:
            self._sessions[user_id] = session_id

    async def drop(self, user_id: UserId) -> None:
        async with self._lock:
            self._sessions.pop(user_id, None)
