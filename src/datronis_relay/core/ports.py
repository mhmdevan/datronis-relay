from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from datronis_relay.domain.audit import AuditEntry
from datronis_relay.domain.cost import CostSummary
from datronis_relay.domain.ids import SessionId, UserId
from datronis_relay.domain.messages import ClaudeRequest, Platform
from datronis_relay.domain.scheduled_task import ScheduledTask
from datronis_relay.domain.stream_events import StreamEvent


class ClaudeClientProtocol(Protocol):
    """Abstraction over the Claude Agent SDK.

    `stream()` is a regular method that returns an async iterator of
    `StreamEvent`s — one `TextChunk` per text fragment, then exactly one
    final `CompletionEvent` carrying usage totals. Error paths never emit
    a `CompletionEvent`.
    """

    def stream(self, request: ClaudeRequest) -> AsyncIterator[StreamEvent]: ...

    async def aclose(self) -> None: ...


class SessionStoreProtocol(Protocol):
    """Persists per-user Claude session ids."""

    async def get(self, user_id: UserId) -> SessionId | None: ...

    async def set(self, user_id: UserId, session_id: SessionId) -> None: ...

    async def drop(self, user_id: UserId) -> None: ...


class AuditStoreProtocol(Protocol):
    """Append-only audit log writer."""

    async def record(self, entry: AuditEntry) -> None: ...


class CostStoreProtocol(Protocol):
    """Cost ledger reader and writer.

    `record_usage` is additive and keyed by (day, user_id). `summary`
    returns rolled-up totals for today / 7d / 30d / all-time.
    """

    async def record_usage(
        self,
        user_id: UserId,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
    ) -> None: ...

    async def summary(self, user_id: UserId) -> CostSummary: ...


class ScheduledTaskStoreProtocol(Protocol):
    """CRUD + claim interface for scheduled tasks.

    `claim_due_tasks` must be atomic: it selects every task with
    `next_run_at <= now AND is_active = 1`, advances `next_run_at` by
    `interval_seconds`, and returns the claimed tasks in one transaction.
    This prevents a slow dispatch from causing the same task to fire
    twice on the next tick.
    """

    async def create_scheduled_task(
        self,
        user_id: UserId,
        platform: Platform,
        channel_ref: str,
        prompt: str,
        interval_seconds: int,
    ) -> ScheduledTask: ...

    async def list_scheduled_tasks(
        self, user_id: UserId
    ) -> list[ScheduledTask]: ...

    async def delete_scheduled_task(
        self, user_id: UserId, task_id: int
    ) -> bool: ...

    async def count_scheduled_tasks(self, user_id: UserId) -> int: ...

    async def claim_due_tasks(
        self, now: datetime, limit: int = 10
    ) -> list[ScheduledTask]: ...
