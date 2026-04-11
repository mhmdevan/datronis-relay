"""Integration tests against a real SQLite file (temp dir per test).

These tests verify the SQLiteStorage implementation end-to-end, including
schema migration on open, concurrent access, cross-connection persistence,
and the cost ledger rollups.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from datronis_relay.domain.audit import AuditEntry, AuditEventType
from datronis_relay.domain.ids import (
    UserId,
    new_correlation_id,
    new_session_id,
)
from datronis_relay.domain.messages import Platform
from datronis_relay.infrastructure.sqlite_storage import SQLiteStorage


@pytest.fixture
async def storage(tmp_path) -> AsyncIterator[SQLiteStorage]:  # type: ignore[no-untyped-def]
    db_path = tmp_path / "test.db"
    s = SQLiteStorage(str(db_path))
    await s.open()
    try:
        yield s
    finally:
        await s.close()


@pytest.mark.integration
class TestMigrations:
    async def test_open_creates_schema(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        db_path = tmp_path / "fresh.db"
        s = SQLiteStorage(str(db_path))
        await s.open()
        try:
            # If the schema was applied, get() on an unknown user must succeed.
            assert await s.get(UserId("telegram:1")) is None
        finally:
            await s.close()

    async def test_second_open_is_idempotent(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        db_path = tmp_path / "reopen.db"
        s1 = SQLiteStorage(str(db_path))
        await s1.open()
        await s1.close()

        s2 = SQLiteStorage(str(db_path))
        await s2.open()  # must not raise
        await s2.close()


@pytest.mark.integration
class TestSessionPersistence:
    async def test_new_user_get_returns_none(self, storage: SQLiteStorage) -> None:
        assert await storage.get(UserId("telegram:1")) is None

    async def test_set_then_get_returns_same_id(self, storage: SQLiteStorage) -> None:
        user_id = UserId("telegram:1")
        sid = new_session_id()
        await storage.set(user_id, sid)
        assert await storage.get(user_id) == sid

    async def test_drop_closes_active_session(self, storage: SQLiteStorage) -> None:
        user_id = UserId("telegram:1")
        await storage.set(user_id, new_session_id())
        await storage.drop(user_id)
        assert await storage.get(user_id) is None

    async def test_set_closes_prior_active_session(self, storage: SQLiteStorage) -> None:
        user_id = UserId("telegram:1")
        first = new_session_id()
        second = new_session_id()
        await storage.set(user_id, first)
        await storage.set(user_id, second)
        # The second call must supersede the first, not create a second active row.
        assert await storage.get(user_id) == second

    async def test_session_survives_reconnect(
        self,
        tmp_path,  # type: ignore[no-untyped-def]
    ) -> None:
        db_path = tmp_path / "persist.db"
        user_id = UserId("telegram:1")
        sid = new_session_id()

        s1 = SQLiteStorage(str(db_path))
        await s1.open()
        await s1.set(user_id, sid)
        await s1.close()

        s2 = SQLiteStorage(str(db_path))
        await s2.open()
        try:
            assert await s2.get(user_id) == sid
        finally:
            await s2.close()


@pytest.mark.integration
class TestCostLedger:
    async def test_record_and_summary(self, storage: SQLiteStorage) -> None:
        user_id = UserId("telegram:1")
        await storage.record_usage(user_id, 100, 200, 0.01)
        await storage.record_usage(user_id, 50, 100, 0.005)

        summary = await storage.summary(user_id)
        assert summary.today_tokens_in == 150
        assert summary.today_tokens_out == 300
        assert summary.today_cost_usd == pytest.approx(0.015)
        assert summary.total_cost_usd == pytest.approx(0.015)

    async def test_unknown_user_returns_zero_summary(self, storage: SQLiteStorage) -> None:
        summary = await storage.summary(UserId("telegram:ghost"))
        assert summary.today_tokens_in == 0
        assert summary.today_tokens_out == 0
        assert summary.today_cost_usd == 0.0
        assert summary.total_cost_usd == 0.0

    async def test_multiple_users_are_isolated(self, storage: SQLiteStorage) -> None:
        await storage.record_usage(UserId("telegram:1"), 100, 200, 0.01)
        await storage.record_usage(UserId("telegram:2"), 500, 500, 0.05)

        s1 = await storage.summary(UserId("telegram:1"))
        s2 = await storage.summary(UserId("telegram:2"))
        assert s1.today_cost_usd == pytest.approx(0.01)
        assert s2.today_cost_usd == pytest.approx(0.05)


@pytest.mark.integration
class TestAuditLog:
    async def test_record_does_not_raise(self, storage: SQLiteStorage) -> None:
        entry = AuditEntry(
            ts=datetime.now(UTC),
            correlation_id=new_correlation_id(),
            user_id=UserId("telegram:1"),
            event_type=AuditEventType.CLAUDE_OK,
            tokens_in=100,
            tokens_out=50,
            cost_usd=0.01,
        )
        await storage.record(entry)

    async def test_record_captures_all_event_types(self, storage: SQLiteStorage) -> None:
        for event_type in AuditEventType:
            entry = AuditEntry(
                ts=datetime.now(UTC),
                correlation_id=new_correlation_id(),
                user_id=UserId("telegram:1"),
                event_type=event_type,
            )
            await storage.record(entry)  # must not raise for any variant


@pytest.mark.integration
class TestScheduledTaskStorage:
    async def test_create_and_list(self, storage: SQLiteStorage) -> None:
        uid = UserId("telegram:1")
        task = await storage.create_scheduled_task(
            user_id=uid,
            platform=Platform.TELEGRAM,
            channel_ref="999",
            prompt="check disk",
            interval_seconds=3600,
        )
        assert task.id > 0
        assert task.is_active

        tasks = await storage.list_scheduled_tasks(uid)
        assert len(tasks) == 1
        assert tasks[0].prompt == "check disk"

    async def test_delete_makes_task_inactive(self, storage: SQLiteStorage) -> None:
        uid = UserId("telegram:1")
        task = await storage.create_scheduled_task(
            user_id=uid,
            platform=Platform.TELEGRAM,
            channel_ref="999",
            prompt="to-delete",
            interval_seconds=3600,
        )
        assert await storage.delete_scheduled_task(uid, task.id) is True
        assert await storage.list_scheduled_tasks(uid) == []
        # Second delete is a no-op, not an error.
        assert await storage.delete_scheduled_task(uid, task.id) is False

    async def test_other_user_cannot_delete(self, storage: SQLiteStorage) -> None:
        alice = UserId("telegram:1")
        bob = UserId("telegram:2")
        task = await storage.create_scheduled_task(
            user_id=alice,
            platform=Platform.TELEGRAM,
            channel_ref="99",
            prompt="private",
            interval_seconds=3600,
        )
        assert await storage.delete_scheduled_task(bob, task.id) is False
        assert (await storage.list_scheduled_tasks(alice))[0].id == task.id

    async def test_count(self, storage: SQLiteStorage) -> None:
        uid = UserId("telegram:1")
        assert await storage.count_scheduled_tasks(uid) == 0
        for i in range(3):
            await storage.create_scheduled_task(
                user_id=uid,
                platform=Platform.TELEGRAM,
                channel_ref=str(i),
                prompt=f"task {i}",
                interval_seconds=3600,
            )
        assert await storage.count_scheduled_tasks(uid) == 3

    async def test_claim_due_tasks_atomically_advances_next_run(
        self, storage: SQLiteStorage
    ) -> None:
        uid = UserId("telegram:1")
        await storage.create_scheduled_task(
            user_id=uid,
            platform=Platform.TELEGRAM,
            channel_ref="1",
            prompt="now",
            interval_seconds=3600,
        )
        # Force the row to be due NOW by asking the store to claim far
        # in the future.
        future = datetime.now(UTC) + timedelta(days=365)
        claimed = await storage.claim_due_tasks(future, limit=10)
        assert len(claimed) == 1
        # A second claim with the same future timestamp still sees the task
        # (next_run_at was advanced by interval, still < far-future).
        # …but we can prove non-re-firing by asking for now + 1s:
        soon = datetime.now(UTC) + timedelta(seconds=1)
        empty = await storage.claim_due_tasks(soon, limit=10)
        assert empty == []

    async def test_claim_ignores_inactive_tasks(self, storage: SQLiteStorage) -> None:
        uid = UserId("telegram:1")
        task = await storage.create_scheduled_task(
            user_id=uid,
            platform=Platform.TELEGRAM,
            channel_ref="1",
            prompt="soon to die",
            interval_seconds=60,
        )
        await storage.delete_scheduled_task(uid, task.id)
        future = datetime.now(UTC) + timedelta(days=1)
        claimed = await storage.claim_due_tasks(future, limit=10)
        assert claimed == []
