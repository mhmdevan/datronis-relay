"""Phase 2 concurrency/load simulation.

Fires 100 dispatches at the router in parallel against in-memory fakes
and verifies:
  - every dispatch completes (no deadlock, no swallowed errors)
  - the rate limiter doesn't false-reject under concurrency
  - total wall time stays within a generous budget
  - the cost ledger records exactly one completion per dispatch

This isn't a real production load test — it proves the core path doesn't
serialize badly and that the per-user locks/fakes behave under concurrency.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from datronis_relay.core.command_router import CommandRouter, StreamReply
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from tests.conftest import FakeClaude, FakeCostStore, make_message, make_user

CONCURRENCY = 100
WALL_TIME_BUDGET_SECONDS = 5.0


@pytest.mark.integration
class TestLoad:
    async def test_one_hundred_concurrent_asks_complete(self) -> None:
        claude = FakeClaude(script=["ok"])
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
        # Budget deliberately generous — the rate limiter must not be the
        # bottleneck for the test itself.
        user = make_user(per_minute=10_000, per_day=10_000_000)

        async def dispatch_one(idx: int) -> None:
            reply = await router.dispatch(
                make_message(f"question {idx}", user_id=user.id), user
            )
            assert isinstance(reply, StreamReply)
            collected = "".join([c async for c in reply.chunks])
            assert collected == "ok"

        start = time.perf_counter()
        await asyncio.gather(*[dispatch_one(i) for i in range(CONCURRENCY)])
        elapsed = time.perf_counter() - start

        assert claude.call_count == CONCURRENCY
        assert len(store.records) == CONCURRENCY
        assert (
            elapsed < WALL_TIME_BUDGET_SECONDS
        ), f"100 dispatches took {elapsed:.2f}s, expected <{WALL_TIME_BUDGET_SECONDS}s"

    async def test_rate_limit_is_enforced_under_concurrency(self) -> None:
        claude = FakeClaude(script=["ok"])
        store = FakeCostStore()
        tracker = CostTracker(
            store=store,
            pricing={},
            default_model="claude-sonnet-4-6",
        )
        router = CommandRouter(
            claude=claude,
            sessions=SessionManager(InMemorySessionStore()),
            rate_limiter=RateLimiter(),
            cost_tracker=tracker,
        )
        user = make_user(per_minute=10, per_day=100_000)

        async def dispatch_one(idx: int) -> bool:
            try:
                reply = await router.dispatch(
                    make_message(f"q{idx}", user_id=user.id), user
                )
                assert isinstance(reply, StreamReply)
                _ = [c async for c in reply.chunks]
                return True
            except Exception:
                return False

        # 30 concurrent asks; only 10 should succeed (per-minute bucket).
        results = await asyncio.gather(*[dispatch_one(i) for i in range(30)])
        assert sum(results) == 10
        assert claude.call_count == 10
