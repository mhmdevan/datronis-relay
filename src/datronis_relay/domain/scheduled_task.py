from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from datronis_relay.domain.ids import UserId
from datronis_relay.domain.messages import Platform


@dataclass(frozen=True, slots=True)
class ScheduledTask:
    """A recurring prompt scheduled by a user.

    `channel_ref` is a platform-specific identifier the adapter uses to
    reconstruct a `ReplyChannel` when the task fires (Telegram: chat_id
    as a string; Slack: channel_id).

    `next_run_at` is the next wall-clock time the task should fire. The
    scheduler claims due tasks by selecting rows with `next_run_at <= now`,
    then advances `next_run_at` by `interval_seconds`.
    """

    id: int
    user_id: UserId
    platform: Platform
    channel_ref: str
    prompt: str
    interval_seconds: int
    next_run_at: datetime
    created_at: datetime
    is_active: bool = True
