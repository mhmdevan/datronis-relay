from __future__ import annotations

from dataclasses import dataclass

from datronis_relay.domain.ids import UserId


@dataclass(frozen=True, slots=True)
class User:
    """An authenticated user with their permissions and rate-limit quotas.

    Instances are built at composition time from the YAML config and never
    mutated. The `id` is always namespaced as `"<platform>:<platform_uid>"`
    so the same numeric id cannot collide across platforms.
    """

    id: UserId
    display_name: str | None
    allowed_tools: frozenset[str]
    rate_limit_per_minute: int
    rate_limit_per_day: int
