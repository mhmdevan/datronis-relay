from __future__ import annotations

import pytest

from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.ids import UserId
from datronis_relay.infrastructure.session_store import InMemorySessionStore


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(InMemorySessionStore())


class TestSessionManager:
    async def test_creates_new_session_on_first_call(
        self, manager: SessionManager
    ) -> None:
        sid = await manager.get_or_create(UserId("u1"))
        assert sid

    async def test_second_call_returns_same_session(
        self, manager: SessionManager
    ) -> None:
        first = await manager.get_or_create(UserId("u1"))
        second = await manager.get_or_create(UserId("u1"))
        assert first == second

    async def test_reset_invalidates_session(
        self, manager: SessionManager
    ) -> None:
        first = await manager.get_or_create(UserId("u1"))
        await manager.reset(UserId("u1"))
        second = await manager.get_or_create(UserId("u1"))
        assert first != second

    async def test_different_users_get_different_sessions(
        self, manager: SessionManager
    ) -> None:
        a = await manager.get_or_create(UserId("u1"))
        b = await manager.get_or_create(UserId("u2"))
        assert a != b

    async def test_reset_of_unknown_user_is_a_noop(
        self, manager: SessionManager
    ) -> None:
        await manager.reset(UserId("never-seen"))  # must not raise

    async def test_session_store_is_concurrency_safe(self) -> None:
        """Interleaved get_or_create calls must all agree on the same id."""
        import asyncio

        manager = SessionManager(InMemorySessionStore())
        results = await asyncio.gather(
            *[manager.get_or_create(UserId("u1")) for _ in range(20)]
        )
        assert len(set(results)) == 1
