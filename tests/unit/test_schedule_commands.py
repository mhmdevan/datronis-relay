"""Tests for the `/schedule`, `/schedules`, `/unschedule` commands."""
from __future__ import annotations

import pytest

from datronis_relay.core.command_router import (
    CommandRouter,
    StaticReply,
)
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.messages import Platform
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from tests.conftest import (
    FakeClaude,
    FakeCostStore,
    FakeScheduledStore,
    make_message,
    make_user,
)


def _router(scheduled_store: FakeScheduledStore | None) -> CommandRouter:
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
    return CommandRouter(
        claude=claude,
        sessions=SessionManager(InMemorySessionStore()),
        rate_limiter=RateLimiter(),
        cost_tracker=tracker,
        scheduled_store=scheduled_store,
        max_scheduled_tasks_per_user=3,
    )


def _msg(text: str, *, channel_ref: str = "chat-1"):
    m = make_message(text)
    # PlatformMessage is frozen; rebuild with channel_ref.
    return m.__class__(
        correlation_id=m.correlation_id,
        platform=Platform.TELEGRAM,
        user_id=m.user_id,
        text=text,
        kind=m.kind,
        received_at=m.received_at,
        attachments=m.attachments,
        channel_ref=channel_ref,
    )


class TestScheduleCommand:
    async def test_creates_a_task(self) -> None:
        store = FakeScheduledStore()
        router = _router(store)
        reply = await router.dispatch(
            _msg("/schedule 1h run the tests"), make_user()
        )
        assert isinstance(reply, StaticReply)
        assert "scheduled task #1" in reply.text
        assert "1h" in reply.text
        assert len(store.tasks) == 1
        task = next(iter(store.tasks.values()))
        assert task.interval_seconds == 3600
        assert task.prompt == "run the tests"

    async def test_invalid_interval(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(
            _msg("/schedule 1y do something"), make_user()
        )
        assert isinstance(reply, StaticReply)
        assert "invalid interval" in reply.text.lower()

    async def test_interval_too_short(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(
            _msg("/schedule 5s ping"), make_user()
        )
        assert isinstance(reply, StaticReply)
        assert "too short" in reply.text.lower()

    async def test_missing_prompt(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(
            _msg("/schedule 1h"), make_user()
        )
        assert isinstance(reply, StaticReply)
        assert "usage" in reply.text.lower()

    async def test_per_user_limit_enforced(self) -> None:
        store = FakeScheduledStore()
        router = _router(store)
        user = make_user()
        # max_scheduled_tasks_per_user is 3 in _router
        for i in range(3):
            await router.dispatch(
                _msg(f"/schedule 1h task {i}"), user
            )
        reply = await router.dispatch(
            _msg("/schedule 1h overflow"), user
        )
        assert isinstance(reply, StaticReply)
        assert "max" in reply.text.lower()

    async def test_without_store_returns_disabled_message(self) -> None:
        router = _router(None)
        reply = await router.dispatch(
            _msg("/schedule 1h ping"), make_user()
        )
        assert isinstance(reply, StaticReply)
        assert "disabled" in reply.text.lower()

    async def test_without_channel_ref_rejected(self) -> None:
        store = FakeScheduledStore()
        router = _router(store)
        reply = await router.dispatch(
            _msg("/schedule 1h ping", channel_ref=""), make_user()
        )
        assert isinstance(reply, StaticReply)
        assert "chat channel" in reply.text.lower()
        assert len(store.tasks) == 0


class TestSchedulesList:
    async def test_empty_list(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(_msg("/schedules"), make_user())
        assert isinstance(reply, StaticReply)
        assert "no scheduled" in reply.text.lower()

    async def test_shows_created_tasks(self) -> None:
        store = FakeScheduledStore()
        router = _router(store)
        user = make_user()
        await router.dispatch(_msg("/schedule 1h first task"), user)
        await router.dispatch(_msg("/schedule 30m second task"), user)

        reply = await router.dispatch(_msg("/schedules"), user)
        assert isinstance(reply, StaticReply)
        assert "first task" in reply.text
        assert "second task" in reply.text
        assert "1h" in reply.text
        assert "30m" in reply.text


class TestUnschedule:
    async def test_delete_existing(self) -> None:
        store = FakeScheduledStore()
        router = _router(store)
        user = make_user()
        await router.dispatch(_msg("/schedule 1h ping"), user)
        reply = await router.dispatch(_msg("/unschedule 1"), user)
        assert isinstance(reply, StaticReply)
        assert "deleted" in reply.text.lower()
        assert await store.count_scheduled_tasks(user.id) == 0

    async def test_delete_nonexistent(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(_msg("/unschedule 999"), make_user())
        assert isinstance(reply, StaticReply)
        assert "no task" in reply.text.lower()

    async def test_requires_numeric_id(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(_msg("/unschedule abc"), make_user())
        assert isinstance(reply, StaticReply)
        assert "invalid task id" in reply.text.lower()

    async def test_missing_id_shows_usage(self) -> None:
        router = _router(FakeScheduledStore())
        reply = await router.dispatch(_msg("/unschedule"), make_user())
        assert isinstance(reply, StaticReply)
        assert "usage" in reply.text.lower()

    async def test_cannot_delete_other_users_task(self) -> None:
        """User A creates, user B tries to delete → fails."""
        store = FakeScheduledStore()
        router = _router(store)
        alice = make_user(user_id="telegram:1")
        bob = make_user(user_id="telegram:2")
        await router.dispatch(_msg("/schedule 1h private"), alice)
        reply = await router.dispatch(_msg("/unschedule 1"), bob)
        assert isinstance(reply, StaticReply)
        assert "no task" in reply.text.lower()
