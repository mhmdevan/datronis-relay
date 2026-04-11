#!/usr/bin/env python3
"""Standalone benchmark runner for datronis-relay.

Measures three categories:
  1. dispatch    — `MessagePipeline.process` overhead with in-memory stores
                   and a zero-latency FakeClaude.
  2. sqlite      — hot-path latency for the session, cost, and scheduled-task
                   tables against a real SQLite file in a temp directory.
  3. concurrency — sustained throughput under concurrent `asyncio.gather`.

Output is a markdown table to stdout suitable for pasting into
`docs/performance.md` or a release note. The runner has no dependencies
beyond what's in `.[dev]`.

Usage:
    python scripts/benchmark.py
    python scripts/benchmark.py --iterations 50000
    python scripts/benchmark.py --only dispatch
    python scripts/benchmark.py --only sqlite
    python scripts/benchmark.py --only concurrency
"""
from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import tempfile
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.command_router import CommandRouter
from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.ports import ClaudeClientProtocol
from datronis_relay.core.rate_limiter import RateLimiter
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.core.session_manager import SessionManager
from datronis_relay.domain.ids import UserId, new_correlation_id
from datronis_relay.domain.messages import (
    ClaudeRequest,
    MessageKind,
    Platform,
    PlatformMessage,
)
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.domain.stream_events import (
    CompletionEvent,
    StreamEvent,
    TextChunk,
    Usage,
)
from datronis_relay.domain.user import User
from datronis_relay.infrastructure.session_store import InMemorySessionStore
from datronis_relay.infrastructure.sqlite_storage import SQLiteStorage


# -----------------------------------------------------------------------------
# Fakes
# -----------------------------------------------------------------------------


class _ZeroLatencyClaude(ClaudeClientProtocol):
    """A Claude client that instantly returns a fixed response."""

    def stream(self, request: ClaudeRequest) -> AsyncIterator[StreamEvent]:
        return self._stream()

    async def _stream(self) -> AsyncIterator[StreamEvent]:
        yield TextChunk(text="ok")
        yield CompletionEvent(
            usage=Usage(tokens_in=10, tokens_out=10, cost_usd=0.0)
        )

    async def aclose(self) -> None:
        return None


class _NullChannel(ReplyChannel):
    max_message_length: int = 4000

    async def send_text(self, text: str) -> None:
        return None

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        return _NoopCtx()


class _NoopCtx(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class _NullCostStore:
    async def record_usage(
        self,
        user_id: UserId,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None:
        return None

    async def summary(self, user_id: UserId) -> object:  # pragma: no cover
        raise NotImplementedError


# -----------------------------------------------------------------------------
# Result helpers
# -----------------------------------------------------------------------------


@dataclass
class LatencyResult:
    label: str
    iterations: int
    p50_ms: float
    p95_ms: float
    p99_ms: float

    @classmethod
    def from_samples(cls, label: str, samples: list[float]) -> "LatencyResult":
        samples_ms = sorted(s * 1000.0 for s in samples)
        n = len(samples_ms)
        return cls(
            label=label,
            iterations=n,
            p50_ms=_percentile(samples_ms, 50),
            p95_ms=_percentile(samples_ms, 95),
            p99_ms=_percentile(samples_ms, 99),
        )


@dataclass
class ThroughputResult:
    concurrency: int
    total_ops: int
    wall_time_s: float
    ops_per_sec: float
    p95_per_op_ms: float


def _percentile(sorted_samples: list[float], pct: int) -> float:
    if not sorted_samples:
        return 0.0
    k = max(0, min(len(sorted_samples) - 1, int(len(sorted_samples) * pct / 100)))
    return sorted_samples[k]


async def _time_async(fn: Callable[[], Awaitable[None]], iterations: int) -> list[float]:
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        await fn()
        samples.append(time.perf_counter() - start)
    return samples


# -----------------------------------------------------------------------------
# Benchmarks
# -----------------------------------------------------------------------------


def _make_user() -> User:
    return User(
        id=UserId("telegram:1"),
        display_name="bench",
        allowed_tools=frozenset(),
        rate_limit_per_minute=1_000_000,
        rate_limit_per_day=1_000_000_000,
    )


def _make_message(text: str, user: User) -> PlatformMessage:
    return PlatformMessage(
        correlation_id=new_correlation_id(),
        platform=Platform.TELEGRAM,
        user_id=user.id,
        text=text,
        kind=MessageKind.TEXT,
        channel_ref="1",
    )


def _build_pipeline() -> MessagePipeline:
    claude = _ZeroLatencyClaude()
    tracker = CostTracker(
        store=_NullCostStore(),  # type: ignore[arg-type]
        pricing={
            "claude-sonnet-4-6": ModelPricing(3.0, 15.0),
        },
        default_model="claude-sonnet-4-6",
    )
    router = CommandRouter(
        claude=claude,
        sessions=SessionManager(InMemorySessionStore()),
        rate_limiter=RateLimiter(),
        cost_tracker=tracker,
    )
    return MessagePipeline(
        auth=AuthGuard(users=[_make_user()]),
        router=router,
    )


async def bench_dispatch(iterations: int) -> list[LatencyResult]:
    pipeline = _build_pipeline()
    user = _make_user()
    channel = _NullChannel()

    async def _static() -> None:
        await pipeline.process(_make_message("/help", user), channel)

    async def _stream() -> None:
        await pipeline.process(_make_message("ping", user), channel)

    static_samples = await _time_async(_static, iterations)
    stream_samples = await _time_async(_stream, iterations)

    return [
        LatencyResult.from_samples(
            "pipeline.process (/help static reply)", static_samples
        ),
        LatencyResult.from_samples(
            "pipeline.process (stream reply, fake claude)", stream_samples
        ),
    ]


async def bench_sqlite(iterations: int) -> list[LatencyResult]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "bench.db"
        storage = SQLiteStorage(str(db_path))
        await storage.open()
        try:
            user = UserId("telegram:bench")

            # Prime a session row so `get` has something to return.
            from datronis_relay.domain.ids import new_session_id

            await storage.set(user, new_session_id())

            async def _session_get() -> None:
                await storage.get(user)

            async def _session_set() -> None:
                await storage.set(user, new_session_id())

            async def _cost_record() -> None:
                await storage.record_usage(user, 100, 200, 0.005)

            async def _cost_summary() -> None:
                await storage.summary(user)

            async def _sched_create() -> None:
                await storage.create_scheduled_task(
                    user_id=user,
                    platform=Platform.TELEGRAM,
                    channel_ref="1",
                    prompt="bench",
                    interval_seconds=3600,
                )

            async def _sched_list() -> None:
                await storage.list_scheduled_tasks(user)

            # claim_due_tasks with a timestamp that never finds anything
            from datetime import UTC, datetime

            past = datetime(2020, 1, 1, tzinfo=UTC)

            async def _sched_claim_empty() -> None:
                await storage.claim_due_tasks(past, limit=10)

            results = [
                LatencyResult.from_samples(
                    "session_store.get (warm)",
                    await _time_async(_session_get, iterations),
                ),
                LatencyResult.from_samples(
                    "session_store.set",
                    await _time_async(_session_set, iterations),
                ),
                LatencyResult.from_samples(
                    "cost_store.record_usage",
                    await _time_async(_cost_record, iterations),
                ),
                LatencyResult.from_samples(
                    "cost_store.summary",
                    await _time_async(_cost_summary, iterations),
                ),
                LatencyResult.from_samples(
                    "scheduled.create_scheduled_task",
                    await _time_async(_sched_create, iterations),
                ),
                LatencyResult.from_samples(
                    "scheduled.list_scheduled_tasks",
                    await _time_async(_sched_list, iterations),
                ),
                LatencyResult.from_samples(
                    "scheduled.claim_due_tasks (empty)",
                    await _time_async(_sched_claim_empty, iterations),
                ),
            ]
            return results
        finally:
            await storage.close()


async def bench_concurrency(iterations: int) -> list[ThroughputResult]:
    pipeline = _build_pipeline()
    user = _make_user()

    async def _one() -> float:
        channel = _NullChannel()
        start = time.perf_counter()
        await pipeline.process(_make_message("ping", user), channel)
        return time.perf_counter() - start

    results: list[ThroughputResult] = []
    # Keep the total ops in the same ballpark across concurrency levels so
    # the wall-time measurement means something.
    for concurrency in (1, 10, 100):
        # total ops ~= iterations, split across `concurrency` parallel workers
        per_worker = max(1, iterations // max(1, concurrency))
        start = time.perf_counter()
        all_samples: list[float] = []
        for _ in range(per_worker):
            batch = await asyncio.gather(*[_one() for _ in range(concurrency)])
            all_samples.extend(batch)
        wall = time.perf_counter() - start
        total_ops = per_worker * concurrency
        sorted_samples = sorted(s * 1000.0 for s in all_samples)
        results.append(
            ThroughputResult(
                concurrency=concurrency,
                total_ops=total_ops,
                wall_time_s=wall,
                ops_per_sec=total_ops / wall if wall > 0 else 0.0,
                p95_per_op_ms=_percentile(sorted_samples, 95),
            )
        )
    return results


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------


def _print_latency_table(title: str, rows: list[LatencyResult]) -> None:
    print(f"\n### {title}\n")
    print("| Operation | Iterations | p50 (ms) | p95 (ms) | p99 (ms) |")
    print("|---|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row.label} | {row.iterations} | "
            f"{row.p50_ms:.3f} | {row.p95_ms:.3f} | {row.p99_ms:.3f} |"
        )


def _print_throughput_table(rows: list[ThroughputResult]) -> None:
    print("\n### Concurrency throughput\n")
    print("| Concurrency | Total ops | Wall time (s) | Ops/sec | p95 per op (ms) |")
    print("|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row.concurrency} | {row.total_ops} | "
            f"{row.wall_time_s:.3f} | {row.ops_per_sec:.1f} | "
            f"{row.p95_per_op_ms:.3f} |"
        )


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------


async def main() -> None:
    parser = argparse.ArgumentParser(description="datronis-relay benchmarks")
    parser.add_argument(
        "--iterations",
        type=int,
        default=2_000,
        help="iterations per benchmark (default: 2000)",
    )
    parser.add_argument(
        "--only",
        choices=["dispatch", "sqlite", "concurrency"],
        help="run only one benchmark category",
    )
    args = parser.parse_args()

    print(f"# datronis-relay benchmarks\n")
    print(f"- Iterations per operation: **{args.iterations}**")
    print(f"- Python: {sys.version.split()[0]}")

    run_all = args.only is None

    if run_all or args.only == "dispatch":
        rows = await bench_dispatch(args.iterations)
        _print_latency_table("Dispatch latency", rows)

    if run_all or args.only == "sqlite":
        rows = await bench_sqlite(args.iterations)
        _print_latency_table("SQLite hot-path latency", rows)

    if run_all or args.only == "concurrency":
        trows = await bench_concurrency(args.iterations)
        _print_throughput_table(trows)


if __name__ == "__main__":
    asyncio.run(main())
