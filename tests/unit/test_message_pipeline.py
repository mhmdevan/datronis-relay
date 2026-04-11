from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import TracebackType

import pytest

from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.command_router import CommandRouter
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from tests.conftest import FakeClaude, FakeCostStore, make_message, make_user

ALLOWED_USER = "telegram:42"


class FakeReplyChannel(ReplyChannel):
    """Capturing reply channel used across pipeline tests."""

    max_message_length: int = 4000

    def __init__(self, *, fail_on_send: bool = False, limit: int = 4000) -> None:
        self.sent: list[str] = []
        self.typing_enter_count = 0
        self.typing_exit_count = 0
        self._fail_on_send = fail_on_send
        self.max_message_length = limit

    async def send_text(self, text: str) -> None:
        if self._fail_on_send:
            raise RuntimeError("simulated send failure")
        self.sent.append(text)

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        return _FakeTypingIndicator(self)


class _FakeTypingIndicator(AbstractAsyncContextManager[None]):
    def __init__(self, channel: FakeReplyChannel) -> None:
        self._channel = channel

    async def __aenter__(self) -> None:
        self._channel.typing_enter_count += 1
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._channel.typing_exit_count += 1
        return None


def _build_pipeline(claude: FakeClaude) -> MessagePipeline:
    store = FakeCostStore()
    tracker = CostTracker(
        store=store,
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
    auth = AuthGuard(users=[make_user(user_id=ALLOWED_USER)])
    return MessagePipeline(auth=auth, router=router)


class TestStaticReply:
    async def test_help_command_is_sent_as_text(self) -> None:
        pipeline = _build_pipeline(FakeClaude(script=["never called"]))
        channel = FakeReplyChannel()

        await pipeline.process(make_message("/help", user_id=ALLOWED_USER), channel)

        assert len(channel.sent) == 1
        assert "/ask" in channel.sent[0]
        # Static replies never activate the typing indicator.
        assert channel.typing_enter_count == 0

    async def test_long_static_reply_is_chunked(self) -> None:
        pipeline = _build_pipeline(FakeClaude(script=["unused"]))
        channel = FakeReplyChannel(limit=100)
        # /help is already multi-line; force the chunking path by dispatching
        # the help text through a custom narrow channel.
        await pipeline.process(make_message("/help", user_id=ALLOWED_USER), channel)
        assert len(channel.sent) >= 2
        for chunk in channel.sent:
            assert len(chunk) <= 100


class TestStreamReply:
    async def test_stream_reply_drains_and_sends_full_text(self) -> None:
        claude = FakeClaude(script=["hello ", "world"])
        pipeline = _build_pipeline(claude)
        channel = FakeReplyChannel()

        await pipeline.process(make_message("say hi", user_id=ALLOWED_USER), channel)

        assert "".join(channel.sent) == "hello world"
        assert channel.typing_enter_count == 1
        assert channel.typing_exit_count == 1

    async def test_stream_reply_chunks_with_channel_limit(self) -> None:
        claude = FakeClaude(script=["x" * 500])
        pipeline = _build_pipeline(claude)
        channel = FakeReplyChannel(limit=100)

        await pipeline.process(make_message("go", user_id=ALLOWED_USER), channel)

        assert len(channel.sent) >= 5  # 500 chars / 100 per chunk
        for chunk in channel.sent:
            assert len(chunk) <= 100

    async def test_empty_stream_falls_back_to_placeholder(self) -> None:
        claude = FakeClaude(script=["", "   ", ""])
        pipeline = _build_pipeline(claude)
        channel = FakeReplyChannel()

        await pipeline.process(make_message("ping", user_id=ALLOWED_USER), channel)

        assert channel.sent == ["(claude returned no content)"]
        assert channel.typing_enter_count == 1


class TestErrorMapping:
    async def test_unauthorized_user_gets_auth_message(self) -> None:
        pipeline = _build_pipeline(FakeClaude(script=["never called"]))
        channel = FakeReplyChannel()

        await pipeline.process(make_message("hi", user_id="telegram:999"), channel)

        assert len(channel.sent) == 1
        assert channel.sent[0].startswith("[AUTH]")

    async def test_rate_limit_exhaustion_surfaces_to_user(self) -> None:
        claude = FakeClaude(script=["ok"])
        store = FakeCostStore()
        tracker = CostTracker(
            store=store, pricing={}, default_model="claude-sonnet-4-6"
        )
        router = CommandRouter(
            claude=claude,
            sessions=SessionManager(InMemorySessionStore()),
            rate_limiter=RateLimiter(),
            cost_tracker=tracker,
        )
        # Build a pipeline whose single user has per_minute=1 so the second
        # dispatch trips the limiter.
        auth = AuthGuard(
            users=[make_user(user_id=ALLOWED_USER, per_minute=1, per_day=100)]
        )
        pipeline = MessagePipeline(auth=auth, router=router)

        channel = FakeReplyChannel()
        await pipeline.process(make_message("first", user_id=ALLOWED_USER), channel)
        await pipeline.process(make_message("second", user_id=ALLOWED_USER), channel)

        # Second response must be the rate-limit user message, not Claude text.
        assert any(s.startswith("[RATE_LIMIT]") for s in channel.sent)

    async def test_send_failure_in_error_path_is_swallowed(self) -> None:
        pipeline = _build_pipeline(FakeClaude(script=["never called"]))
        channel = FakeReplyChannel(fail_on_send=True)

        # Must not raise — `_safe_send` catches channel errors.
        await pipeline.process(make_message("hi", user_id="telegram:999"), channel)


class TestContextvarHygiene:
    async def test_correlation_is_cleared_after_each_call(self) -> None:
        import structlog

        pipeline = _build_pipeline(FakeClaude(script=["ok"]))
        channel = FakeReplyChannel()

        await pipeline.process(make_message("hi", user_id=ALLOWED_USER), channel)

        ctx = structlog.contextvars.get_contextvars()
        assert "correlation_id" not in ctx
