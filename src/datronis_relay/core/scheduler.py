from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Protocol

import structlog

from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.ports import ScheduledTaskStoreProtocol
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.domain.ids import new_correlation_id
from datronis_relay.domain.messages import (
    MessageKind,
    Platform,
    PlatformMessage,
)
from datronis_relay.domain.scheduled_task import ScheduledTask

log = structlog.get_logger(__name__)


class ChatAdapterForDelivery(Protocol):
    """Structural adapter type the scheduler needs for out-of-band delivery.

    Every adapter already implements this method in Phase 4 — it's used
    by the scheduler to reconstruct a reply channel from the stored
    `channel_ref`.
    """

    def build_reply_channel(self, channel_ref: str) -> ReplyChannel: ...


class AdapterRegistry:
    """Platform → adapter lookup, populated at composition time.

    The scheduler uses this to reconstruct a reply channel for a
    scheduled task without holding a reference to a specific adapter
    class. Future adapters just register themselves in `main.py`.
    """

    def __init__(
        self, adapters: dict[Platform, ChatAdapterForDelivery]
    ) -> None:
        self._adapters = adapters

    def get(self, platform: Platform) -> ChatAdapterForDelivery | None:
        return self._adapters.get(platform)


class Scheduler:
    """Background worker that fires scheduled tasks through the pipeline.

    Design:
      - Poll every `poll_interval_seconds` (default 30s).
      - Atomically claim up to `batch_limit` due tasks via the store.
      - For each claimed task, reconstruct a `ReplyChannel` via the
        adapter registry and run it through `MessagePipeline.process`
        with a synthetic `PlatformMessage`.
      - Reuse the pipeline for rate limiting + cost tracking + error
        mapping — the scheduler does not have a parallel code path.

    One tick dispatches tasks concurrently as fire-and-forget asyncio
    tasks. The worker never blocks on slow Claude calls.
    """

    def __init__(
        self,
        store: ScheduledTaskStoreProtocol,
        pipeline: MessagePipeline,
        registry: AdapterRegistry,
        poll_interval_seconds: float = 30.0,
        batch_limit: int = 10,
    ) -> None:
        self._store = store
        self._pipeline = pipeline
        self._registry = registry
        self._poll_interval = poll_interval_seconds
        self._batch_limit = batch_limit

    async def run_forever(self) -> None:
        log.info("scheduler.start", poll_interval=self._poll_interval)
        try:
            while True:
                try:
                    await self.tick()
                except Exception as exc:  # noqa: BLE001
                    log.exception("scheduler.tick_failed", error=str(exc))
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            log.info("scheduler.stop")
            raise

    async def tick(self) -> int:
        """Claim and dispatch all currently due tasks. Returns the count."""
        now = datetime.now(UTC)
        tasks = await self._store.claim_due_tasks(now=now, limit=self._batch_limit)
        for task in tasks:
            asyncio.create_task(
                self._dispatch(task),
                name=f"scheduled-task-{task.id}",
            )
        return len(tasks)

    async def _dispatch(self, task: ScheduledTask) -> None:
        adapter = self._registry.get(task.platform)
        if adapter is None:
            log.warning(
                "scheduler.no_adapter",
                task_id=task.id,
                platform=task.platform.value,
            )
            return
        try:
            channel = adapter.build_reply_channel(task.channel_ref)
        except Exception as exc:  # noqa: BLE001
            log.exception(
                "scheduler.channel_build_failed",
                task_id=task.id,
                error=str(exc),
            )
            return

        synthetic = PlatformMessage(
            correlation_id=new_correlation_id(),
            platform=task.platform,
            user_id=task.user_id,
            text=task.prompt,
            kind=MessageKind.TEXT,
            channel_ref=task.channel_ref,
        )
        log.info("scheduler.fire", task_id=task.id, user_id=task.user_id)
        await self._pipeline.process(synthetic, channel)
