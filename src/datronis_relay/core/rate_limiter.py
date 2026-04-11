from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from datronis_relay.domain.errors import RateLimitError
from datronis_relay.domain.ids import UserId


@dataclass
class _Bucket:
    """A single token bucket.

    - `capacity`: max tokens the bucket can hold
    - `tokens`: current level
    - `refill_rate_per_sec`: constant refill rate
    - `last_refill`: timestamp of the last refill calculation

    `consume()` refills based on elapsed wall time, then deducts one token
    if possible. Not thread-safe by itself — `RateLimiter` holds a lock.
    """

    capacity: float
    tokens: float
    refill_rate_per_sec: float
    last_refill: datetime

    def consume(self, amount: float = 1.0) -> bool:
        now = datetime.now(UTC)
        elapsed = (now - self.last_refill).total_seconds()
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.refill_rate_per_sec,
        )
        self.last_refill = now
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class RateLimiter:
    """Per-user two-bucket token limiter (per-minute + per-day).

    State lives in memory: rate limits don't need to survive restarts, and
    persistence would add noise to the hot path. Per-user limits come from
    the `User` record, so different users can have different quotas.
    """

    def __init__(self) -> None:
        self._users: dict[UserId, tuple[_Bucket, _Bucket]] = {}
        self._lock = asyncio.Lock()

    async def check(
        self,
        user_id: UserId,
        per_minute: int,
        per_day: int,
    ) -> None:
        """Deduct one token from both buckets.

        Raises `RateLimitError` on either bucket being empty. On a daily
        exhaustion we refund the minute token we just consumed — so back-
        pressure from the daily cap doesn't also burn the minute budget.
        """
        async with self._lock:
            minute_bucket, day_bucket = self._get_or_create(user_id, per_minute, per_day)
            if not minute_bucket.consume():
                raise RateLimitError(f"minute quota exceeded ({per_minute}/min)")
            if not day_bucket.consume():
                minute_bucket.tokens = min(minute_bucket.capacity, minute_bucket.tokens + 1.0)
                raise RateLimitError(f"daily quota exceeded ({per_day}/day)")

    def _get_or_create(
        self,
        user_id: UserId,
        per_minute: int,
        per_day: int,
    ) -> tuple[_Bucket, _Bucket]:
        existing = self._users.get(user_id)
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        minute_bucket = _Bucket(
            capacity=float(per_minute),
            tokens=float(per_minute),
            refill_rate_per_sec=per_minute / 60.0,
            last_refill=now,
        )
        day_bucket = _Bucket(
            capacity=float(per_day),
            tokens=float(per_day),
            refill_rate_per_sec=per_day / 86_400.0,
            last_refill=now,
        )
        self._users[user_id] = (minute_bucket, day_bucket)
        return self._users[user_id]
