from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CostSummary:
    """Rolled-up usage and cost for a single user."""

    today_tokens_in: int
    today_tokens_out: int
    today_cost_usd: float
    week_cost_usd: float
    month_cost_usd: float
    total_cost_usd: float
