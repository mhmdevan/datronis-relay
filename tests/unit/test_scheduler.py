from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager
from types import TracebackType

import pytest

from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.command_router import CommandRouter
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.core.scheduler import AdapterRegistry, Scheduler
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.messages import Platform
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from tests.conftest import (
    FakeClaude,
    FakeCostStore,
    FakeScheduledStore,
    make_user,
)

OWNER_ID = "telegram:42"


class RecordingChannel(ReplyChannel):
    max_message_length: int = 4000

    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        return _Noop()


class _Noop(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class RecordingAdapter:
    """Adapter stub that records which channel_refs it was asked to resolve."""

    def __init__(self) -> None:
        self.last_built: list[str] = []
        self.channel = RecordingChannel()

    def build_reply_channel(self, channel_ref: str) -> ReplyChannel:
        self.last_built.append(channel_ref)
        return self.channel

    async def run_forever(self) -> None:  # not used in these tests
        await asyncio.Event().wait()


def _build_pipeline_and_scheduler() -> tuple[
    Scheduler, FakeScheduledStore, FakeClaude, RecordingAdapter
]:
    claude = FakeClaude(script=["ok"])
    tracker = CostTracker(
        store=FakeCostStore(),
        pricing={
            "claude-sonnet-4-6": ModelPricing(
                input_usd_per_mtok=3.0, output_usd_per_mtok=15.0
            )
        },
        default_model="claude-sonnet-4-6",
    )
    router = CommandRouter(
        claude=claude,
        sessions=SessionManager(InMemorySessionStore()),
        rate_limiter=RateLimiter(),
        cost_tracker=tracker,
    )
    auth = AuthGuard(users=[make_user(user_id=OWNER_ID)])
    pipeline = MessagePipeline(auth=auth, router=router)

    adapter = RecordingAdapter()
    registry = AdapterRegistry(adapters={Platform.TELEGRAM: adapter})
    store = FakeScheduledStore()
    scheduler = Scheduler(
        store=store,
        pipeline=pipeline,
        registry=registry,
        poll_interval_seconds=0.01,
    )
    return scheduler, store, claude, adapter


class TestSchedulerTick:
    async def test_tick_with_no_tasks_returns_zero(self) -> None:
        scheduler, _, _, _ = _build_pipeline_and_scheduler()
        count = await scheduler.tick()
        assert count == 0

    async def test_due_task_is_dispatched_through_pipeline(self) -> None:
        scheduler, store, claude, adapter = _build_pipeline_and_scheduler()

        from datronis_relay.domain.ids import UserId

        await store.create_scheduled_task(
            user_id=UserId(OWNER_ID),
            platform=Platform.TELEGRAM,
            channel_ref="123456",
            prompt="check disk usage",
            interval_seconds=30,
        )
        # Manually mark the task as due right now.
        task = next(iter(store.tasks.values()))
        from datetime import UTC, datetime

        store.tasks[task.id] = task.__class__(
            id=task.id,
            user_id=task.user_id,
            platform=task.platform,
            channel_ref=task.channel_ref,
            prompt=task.prompt,
            interval_seconds=task.interval_seconds,
            next_run_at=datetime.now(UTC),
            created_at=task.created_at,
            is_active=True,
        )

        fired = await scheduler.tick()
        assert fired == 1

        # The tick launches fire-and-forget tasks; give them one scheduler turn.
        for _ in range(10):
            await asyncio.sleep(0)

        assert adapter.last_built == ["123456"]
        assert claude.call_count == 1
        assert claude.last_request is not None
        assert claude.last_request.prompt == "check disk usage"
        assert "ok" in "".join(adapter.channel.sent)

    async def test_scheduler_skips_unknown_platform(self) -> None:
        scheduler, store, claude, adapter = _build_pipeline_and_scheduler()

        from datronis_relay.domain.ids import UserId

        await store.create_scheduled_task(
            user_id=UserId(OWNER_ID),
            platform=Platform.SLACK,  # no adapter registered for SLACK
            channel_ref="C999",
            prompt="test",
            interval_seconds=30,
        )
        from datetime import UTC, datetime

        task = next(iter(store.tasks.values()))
        store.tasks[task.id] = task.__class__(
            id=task.id,
            user_id=task.user_id,
            platform=task.platform,
            channel_ref=task.channel_ref,
            prompt=task.prompt,
            interval_seconds=task.interval_seconds,
            next_run_at=datetime.now(UTC),
            created_at=task.created_at,
            is_active=True,
        )

        await scheduler.tick()
        for _ in range(10):
            await asyncio.sleep(0)

        assert claude.call_count == 0
        assert adapter.last_built == []

    async def test_tick_ignores_future_tasks(self) -> None:
        scheduler, store, claude, _ = _build_pipeline_and_scheduler()

        from datronis_relay.domain.ids import UserId

        # Default FakeScheduledStore.create schedules next_run_at in the future.
        await store.create_scheduled_task(
            user_id=UserId(OWNER_ID),
            platform=Platform.TELEGRAM,
            channel_ref="123456",
            prompt="future",
            interval_seconds=3600,
        )
        fired = await scheduler.tick()
        assert fired == 0
        assert claude.call_count == 0
