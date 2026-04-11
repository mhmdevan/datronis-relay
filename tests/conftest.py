from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import pytest
import structlog

from datronis_relay.core.ports import (
    ClaudeClientProtocol,
    CostStoreProtocol,
    ScheduledTaskStoreProtocol,
)
from datronis_relay.domain.cost import CostSummary
from datronis_relay.domain.ids import UserId, new_correlation_id
from datronis_relay.domain.messages import (
    ClaudeRequest,
    MessageKind,
    Platform,
    PlatformMessage,
)
from datronis_relay.domain.scheduled_task import ScheduledTask
from datronis_relay.domain.stream_events import (
    CompletionEvent,
    StreamEvent,
    TextChunk,
    Usage,
)
from datronis_relay.domain.user import User


@pytest.fixture(autouse=True)
def _clear_structlog_context() -> Iterator[None]:
    """Prevent contextvar leakage between tests."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


class FakeClaude(ClaudeClientProtocol):
    """Phase-2 fake: yields `TextChunk`s from a script, then a final
    `CompletionEvent` with fixed usage numbers.

    `last_request` captures the last request so tests can assert the router
    built it correctly. `call_count` counts how many streams were started.
    """

    def __init__(
        self,
        script: list[str],
        tokens_in: int = 100,
        tokens_out: int = 200,
    ) -> None:
        self.script = script
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.last_request: ClaudeRequest | None = None
        self.call_count: int = 0

    def stream(self, request: ClaudeRequest) -> AsyncIterator[StreamEvent]:
        self.last_request = request
        self.call_count += 1
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[StreamEvent]:
        for part in self.script:
            yield TextChunk(text=part)
        yield CompletionEvent(
            usage=Usage(
                tokens_in=self.tokens_in,
                tokens_out=self.tokens_out,
                cost_usd=0.0,
            )
        )

    async def aclose(self) -> None:
        return None


class FakeCostStore(CostStoreProtocol):
    """In-memory cost store for unit tests that don't need real SQLite."""

    def __init__(self) -> None:
        self.records: list[tuple[UserId, int, int, float]] = []

    async def record_usage(
        self,
        user_id: UserId,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None:
        self.records.append((user_id, tokens_in, tokens_out, cost_usd))

    async def summary(self, user_id: UserId) -> CostSummary:
        rows = [r for r in self.records if r[0] == user_id]
        total_in = sum(r[1] for r in rows)
        total_out = sum(r[2] for r in rows)
        total_cost = sum(r[3] for r in rows)
        return CostSummary(
            today_tokens_in=total_in,
            today_tokens_out=total_out,
            today_cost_usd=total_cost,
            week_cost_usd=total_cost,
            month_cost_usd=total_cost,
            total_cost_usd=total_cost,
        )


class FakeScheduledStore(ScheduledTaskStoreProtocol):
    """In-memory scheduled task store for unit tests."""

    def __init__(self) -> None:
        self.tasks: dict[int, ScheduledTask] = {}
        self._next_id = 1

    async def create_scheduled_task(
        self,
        user_id: UserId,
        platform: Platform,
        channel_ref: str,
        prompt: str,
        interval_seconds: int,
    ) -> ScheduledTask:
        now = datetime.now(UTC)
        task = ScheduledTask(
            id=self._next_id,
            user_id=user_id,
            platform=platform,
            channel_ref=channel_ref,
            prompt=prompt,
            interval_seconds=interval_seconds,
            next_run_at=now + timedelta(seconds=interval_seconds),
            created_at=now,
            is_active=True,
        )
        self.tasks[self._next_id] = task
        self._next_id += 1
        return task

    async def list_scheduled_tasks(self, user_id: UserId) -> list[ScheduledTask]:
        return [t for t in self.tasks.values() if t.user_id == user_id and t.is_active]

    async def delete_scheduled_task(self, user_id: UserId, task_id: int) -> bool:
        task = self.tasks.get(task_id)
        if task is None or task.user_id != user_id or not task.is_active:
            return False
        self.tasks[task_id] = ScheduledTask(
            id=task.id,
            user_id=task.user_id,
            platform=task.platform,
            channel_ref=task.channel_ref,
            prompt=task.prompt,
            interval_seconds=task.interval_seconds,
            next_run_at=task.next_run_at,
            created_at=task.created_at,
            is_active=False,
        )
        return True

    async def count_scheduled_tasks(self, user_id: UserId) -> int:
        return sum(1 for t in self.tasks.values() if t.user_id == user_id and t.is_active)

    async def claim_due_tasks(self, now: datetime, limit: int = 10) -> list[ScheduledTask]:
        due = [t for t in self.tasks.values() if t.is_active and t.next_run_at <= now][:limit]
        for task in due:
            self.tasks[task.id] = ScheduledTask(
                id=task.id,
                user_id=task.user_id,
                platform=task.platform,
                channel_ref=task.channel_ref,
                prompt=task.prompt,
                interval_seconds=task.interval_seconds,
                next_run_at=now + timedelta(seconds=task.interval_seconds),
                created_at=task.created_at,
                is_active=True,
            )
        return due


@pytest.fixture
def fake_claude() -> FakeClaude:
    return FakeClaude(script=["hello ", "world"])


@pytest.fixture
def fake_cost_store() -> FakeCostStore:
    return FakeCostStore()


@pytest.fixture
def fake_scheduled_store() -> FakeScheduledStore:
    return FakeScheduledStore()


def make_message(text: str, user_id: str = "telegram:42") -> PlatformMessage:
    return PlatformMessage(
        correlation_id=new_correlation_id(),
        platform=Platform.TELEGRAM,
        user_id=UserId(user_id),
        text=text,
        kind=MessageKind.TEXT,
    )


def make_user(
    user_id: str = "telegram:42",
    display_name: str | None = "Test User",
    allowed_tools: list[str] | None = None,
    per_minute: int = 1000,
    per_day: int = 100_000,
) -> User:
    return User(
        id=UserId(user_id),
        display_name=display_name,
        allowed_tools=frozenset(allowed_tools or []),
        rate_limit_per_minute=per_minute,
        rate_limit_per_day=per_day,
    )
