from __future__ import annotations

import pytest

from datronis_relay.core.command_router import (
    CommandRouter,
    StaticReply,
    StreamReply,
)
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.errors import RateLimitError
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from tests.conftest import FakeClaude, FakeCostStore, make_message, make_user


def _router(
    claude: FakeClaude,
    *,
    cost_store: FakeCostStore | None = None,
) -> tuple[CommandRouter, FakeCostStore]:
    store = cost_store or FakeCostStore()
    cost_tracker = CostTracker(
        store=store,
        pricing={
            "claude-sonnet-4-6": ModelPricing(
                input_usd_per_mtok=3.0,
                output_usd_per_mtok=15.0,
            ),
        },
        default_model="claude-sonnet-4-6",
    )
    router = CommandRouter(
        claude=claude,
        sessions=SessionManager(InMemorySessionStore()),
        rate_limiter=RateLimiter(),
        cost_tracker=cost_tracker,
    )
    return router, store


@pytest.fixture
def router_and_store(fake_claude: FakeClaude) -> tuple[CommandRouter, FakeCostStore]:
    return _router(fake_claude)


class TestStaticCommands:
    async def test_start_returns_welcome(
        self, router_and_store: tuple[CommandRouter, FakeCostStore]
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("/start"), make_user())
        assert isinstance(reply, StaticReply)
        assert "datronis" in reply.text.lower() or "hello" in reply.text.lower()

    async def test_help_lists_all_commands(
        self, router_and_store: tuple[CommandRouter, FakeCostStore]
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("/help"), make_user())
        assert isinstance(reply, StaticReply)
        for cmd in ("/start", "/help", "/ask", "/status", "/stop", "/cost"):
            assert cmd in reply.text

    async def test_status_returns_session_id(
        self, router_and_store: tuple[CommandRouter, FakeCostStore]
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("/status"), make_user())
        assert isinstance(reply, StaticReply)
        assert reply.text.startswith("session: ")

    async def test_stop_resets_session(
        self, router_and_store: tuple[CommandRouter, FakeCostStore]
    ) -> None:
        router, _ = router_and_store
        user = make_user()
        first = await router.dispatch(make_message("/status"), user)
        assert isinstance(first, StaticReply)
        first_session = first.text

        reset = await router.dispatch(make_message("/stop"), user)
        assert isinstance(reset, StaticReply)
        assert "reset" in reset.text.lower()

        second = await router.dispatch(make_message("/status"), user)
        assert isinstance(second, StaticReply)
        assert second.text != first_session


class TestAskCommand:
    async def test_ask_reaches_claude_and_drains_text(
        self, router_and_store: tuple[CommandRouter, FakeCostStore], fake_claude: FakeClaude
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("/ask what time is it"), make_user())
        assert isinstance(reply, StreamReply)
        collected = "".join([c async for c in reply.chunks])
        assert collected == "hello world"
        assert fake_claude.last_request is not None
        assert fake_claude.last_request.prompt == "what time is it"

    async def test_default_message_is_routed_as_ask(
        self, router_and_store: tuple[CommandRouter, FakeCostStore], fake_claude: FakeClaude
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("explain WAL mode"), make_user())
        assert isinstance(reply, StreamReply)
        _ = [c async for c in reply.chunks]
        assert fake_claude.last_request is not None
        assert fake_claude.last_request.prompt == "explain WAL mode"

    async def test_empty_ask_is_rejected_without_calling_claude(
        self, router_and_store: tuple[CommandRouter, FakeCostStore], fake_claude: FakeClaude
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("/ask   "), make_user())
        assert isinstance(reply, StaticReply)
        assert "nothing" in reply.text.lower()
        assert fake_claude.call_count == 0

    async def test_allowed_tools_are_forwarded_to_claude(
        self, fake_claude: FakeClaude
    ) -> None:
        router, _ = _router(fake_claude)
        user = make_user(allowed_tools=["Read", "Bash"])
        reply = await router.dispatch(make_message("hi"), user)
        assert isinstance(reply, StreamReply)
        _ = [c async for c in reply.chunks]
        assert fake_claude.last_request is not None
        assert fake_claude.last_request.allowed_tools == ("Bash", "Read")  # sorted

    async def test_completion_event_is_recorded_to_cost_store(
        self, fake_claude: FakeClaude
    ) -> None:
        router, store = _router(fake_claude)
        user = make_user()
        reply = await router.dispatch(make_message("hi"), user)
        assert isinstance(reply, StreamReply)
        _ = [c async for c in reply.chunks]
        assert len(store.records) == 1
        assert store.records[0][0] == user.id
        assert store.records[0][1] == fake_claude.tokens_in
        assert store.records[0][2] == fake_claude.tokens_out


class TestCostCommand:
    async def test_cost_command_renders_summary(
        self, fake_claude: FakeClaude
    ) -> None:
        router, _ = _router(fake_claude)
        user = make_user(display_name="Alice")
        # prime the ledger with one ask
        reply = await router.dispatch(make_message("hi"), user)
        assert isinstance(reply, StreamReply)
        _ = [c async for c in reply.chunks]

        cost_reply = await router.dispatch(make_message("/cost"), user)
        assert isinstance(cost_reply, StaticReply)
        assert "Alice" in cost_reply.text
        assert "today" in cost_reply.text
        assert "total" in cost_reply.text


class TestRateLimiting:
    async def test_minute_quota_exceeded_raises_rate_limit_error(
        self, fake_claude: FakeClaude
    ) -> None:
        router, _ = _router(fake_claude)
        user = make_user(per_minute=2, per_day=1000)
        await router.dispatch(make_message("one"), user)
        await router.dispatch(make_message("two"), user)
        with pytest.raises(RateLimitError, match="minute"):
            await router.dispatch(make_message("three"), user)

    async def test_static_commands_do_not_consume_rate_limit(
        self, fake_claude: FakeClaude
    ) -> None:
        router, _ = _router(fake_claude)
        user = make_user(per_minute=1, per_day=1000)
        # exhaust nothing with /status or /help
        for _ in range(10):
            await router.dispatch(make_message("/help"), user)
            await router.dispatch(make_message("/status"), user)
        # /ask still has one token available
        reply = await router.dispatch(make_message("/ask hi"), user)
        assert isinstance(reply, StreamReply)


class TestUnknownCommand:
    async def test_unknown_command_returns_static_error(
        self, router_and_store: tuple[CommandRouter, FakeCostStore]
    ) -> None:
        router, _ = router_and_store
        reply = await router.dispatch(make_message("/bogus"), make_user())
        assert isinstance(reply, StaticReply)
        assert "unknown" in reply.text.lower()
