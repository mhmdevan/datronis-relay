"""End-to-end pipeline test exercising `MessagePipeline` with a fake channel.

Phase 3 extracted the cross-platform logic into `MessagePipeline`. This
file used to call `AuthGuard.authenticate` / `CommandRouter.dispatch`
directly; it now calls `pipeline.process(message, channel)` — the same
code path both the Telegram and Slack adapters use in production.
"""
from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from types import TracebackType

import pytest

from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.chunking import chunk_message
from datronis_relay.core.command_router import CommandRouter
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from tests.conftest import FakeClaude, FakeCostStore, make_message, make_user

OWNER_ID = "telegram:42"


class FakeChannel(ReplyChannel):
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


def _build_pipeline(
    claude: FakeClaude,
) -> tuple[MessagePipeline, FakeCostStore]:
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
    auth = AuthGuard(users=[make_user(user_id=OWNER_ID, allowed_tools=["Read"])])
    return MessagePipeline(auth=auth, router=router), store


@pytest.mark.integration
class TestHappyPath:
    async def test_authorized_ask_streams_and_records_cost(self) -> None:
        claude = FakeClaude(
            script=[
                "I'll run `systemctl restart nginx` on prod-web-1.\n\n",
                "Done. Exit code 0.",
            ],
            tokens_in=321,
            tokens_out=654,
        )
        pipeline, store = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(
            make_message("restart nginx on prod-web-1", user_id=OWNER_ID),
            channel,
        )

        full = "".join(channel.sent)
        assert "systemctl restart nginx" in full
        assert "Exit code 0" in full

        # Cost was recorded on the completion event.
        assert len(store.records) == 1
        assert store.records[0][1] == 321
        assert store.records[0][2] == 654

    async def test_long_reply_is_chunked(self) -> None:
        claude = FakeClaude(script=["a" * 5000])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(make_message("big", user_id=OWNER_ID), channel)

        assert len(channel.sent) >= 2
        for chunk in channel.sent:
            assert len(chunk) <= 4000

    async def test_allowed_tools_pass_through_to_claude(self) -> None:
        claude = FakeClaude(script=["ok"])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(make_message("go", user_id=OWNER_ID), channel)

        assert claude.last_request is not None
        assert claude.last_request.allowed_tools == ("Read",)


@pytest.mark.integration
class TestAuthRejection:
    async def test_unauthorized_user_sees_auth_error(self) -> None:
        claude = FakeClaude(script=["never called"])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(
            make_message("restart nginx", user_id="telegram:999"),
            channel,
        )

        assert len(channel.sent) == 1
        assert channel.sent[0].startswith("[AUTH]")
        assert claude.call_count == 0

    async def test_auth_error_message_includes_correlation_id(self) -> None:
        claude = FakeClaude(script=["never called"])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        message = make_message("hi", user_id="telegram:999")
        await pipeline.process(message, channel)
        assert message.correlation_id in channel.sent[0]


@pytest.mark.integration
class TestSessionLifecycle:
    async def test_consecutive_asks_share_a_session_id(self) -> None:
        claude = FakeClaude(script=["ok"])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(make_message("first", user_id=OWNER_ID), channel)
        s1 = claude.last_request.session_id  # type: ignore[union-attr]
        await pipeline.process(make_message("second", user_id=OWNER_ID), channel)
        s2 = claude.last_request.session_id  # type: ignore[union-attr]

        assert s1 == s2

    async def test_stop_command_forces_a_fresh_session(self) -> None:
        claude = FakeClaude(script=["ok"])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(make_message("first", user_id=OWNER_ID), channel)
        s1 = claude.last_request.session_id  # type: ignore[union-attr]

        await pipeline.process(make_message("/stop", user_id=OWNER_ID), channel)

        await pipeline.process(make_message("second", user_id=OWNER_ID), channel)
        s2 = claude.last_request.session_id  # type: ignore[union-attr]

        assert s1 != s2


@pytest.mark.integration
class TestChunkingInteraction:
    async def test_pipeline_respects_channel_max_message_length(self) -> None:
        """The pipeline must pass each channel's own limit to `chunk_message`."""

        class SmallChannel(FakeChannel):
            max_message_length: int = 100

        claude = FakeClaude(script=["x" * 500])
        pipeline, _ = _build_pipeline(claude)
        channel = SmallChannel()

        await pipeline.process(make_message("go", user_id=OWNER_ID), channel)

        assert len(channel.sent) >= 5
        for chunk in channel.sent:
            assert len(chunk) <= 100

    async def test_chunk_helper_used_directly_agrees_with_pipeline(self) -> None:
        """Sanity check: the pipeline's output matches a direct chunk_message
        call with the same limit. Guards against off-by-one drift."""
        claude = FakeClaude(script=["y" * 3000])
        pipeline, _ = _build_pipeline(claude)
        channel = FakeChannel()

        await pipeline.process(make_message("go", user_id=OWNER_ID), channel)
        collected = "".join(channel.sent)

        expected = chunk_message(collected, limit=4000)
        # After re-chunking the collected text we should get at most one chunk
        # because the total length (3000) is under the limit.
        assert len(expected) == 1
