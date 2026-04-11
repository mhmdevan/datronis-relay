from __future__ import annotations

import re

# Supports: 30s, 5m, 2h, 1d. Case-insensitive.
_PATTERN = re.compile(r"^\s*(\d+)\s*([smhd])\s*$", re.IGNORECASE)

_MULTIPLIERS_SECONDS: dict[str, int] = {
    "s": 1,
    "m": 60,
    "h": 3_600,
    "d": 86_400,
}

MIN_INTERVAL_SECONDS = 30
MAX_INTERVAL_SECONDS = 90 * 86_400  # 90 days


def parse_interval(text: str) -> int:
    """Parse a human interval string into seconds.

    Accepts e.g. `"30s"`, `"5m"`, `"2h"`, `"1d"`. Raises `ValueError` on
    unrecognized formats, values below `MIN_INTERVAL_SECONDS`, or values
    above `MAX_INTERVAL_SECONDS`.

    We deliberately don't support cron for Phase 4 — the parser surface
    is intentionally small.
    """
    match = _PATTERN.match(text)
    if not match:
        raise ValueError(
            f"invalid interval {text!r} — expected format like '30s', '5m', '2h', '1d'"
        )
    value = int(match.group(1))
    unit = match.group(2).lower()
    seconds = value * _MULTIPLIERS_SECONDS[unit]
    if seconds < MIN_INTERVAL_SECONDS:
        raise ValueError(f"interval too short: {seconds}s (minimum {MIN_INTERVAL_SECONDS}s)")
    if seconds > MAX_INTERVAL_SECONDS:
        raise ValueError(f"interval too long: {seconds}s (maximum {MAX_INTERVAL_SECONDS}s)")
    return seconds


def format_interval(seconds: int) -> str:
    """Render a second count as a compact human interval.

    Picks the largest unit that divides evenly; falls back to seconds if
    nothing divides cleanly.
    """
    if seconds % 86_400 == 0:
        return f"{seconds // 86_400}d"
    if seconds % 3_600 == 0:
        return f"{seconds // 3_600}h"
    if seconds % 60 == 0:
        return f"{seconds // 60}m"
    return f"{seconds}s"
