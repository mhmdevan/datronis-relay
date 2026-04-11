from __future__ import annotations

import structlog

from datronis_relay.core.ports import CostStoreProtocol
from datronis_relay.domain.cost import CostSummary
from datronis_relay.domain.ids import UserId
from datronis_relay.domain.pricing import ModelPricing
from datronis_relay.domain.stream_events import Usage

log = structlog.get_logger(__name__)


class CostTracker:
    """Computes USD cost from token counts and records to the ledger.

    Unknown models fall through to cost=0.0 with a warning; we never raise
    because the cost ledger is secondary — a pricing-table miss must not
    break the user's chat flow.
    """

    def __init__(
        self,
        store: CostStoreProtocol,
        pricing: dict[str, ModelPricing],
        default_model: str,
    ) -> None:
        self._store = store
        self._pricing = pricing
        self._default_model = default_model

    async def record(
        self,
        user_id: UserId,
        tokens_in: int,
        tokens_out: int,
        model: str | None = None,
    ) -> Usage:
        model_name = model or self._default_model
        pricing = self._pricing.get(model_name)
        if pricing is None:
            log.warning("cost_tracker.unknown_model", model=model_name)
            cost = 0.0
        else:
            cost = pricing.cost(tokens_in, tokens_out)
        await self._store.record_usage(user_id, tokens_in, tokens_out, cost)
        return Usage(tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost)

    async def summary(self, user_id: UserId) -> CostSummary:
        return await self._store.summary(user_id)
