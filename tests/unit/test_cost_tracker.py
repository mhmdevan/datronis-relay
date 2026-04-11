from __future__ import annotations

import pytest

from datronis_relay.core.cost_tracker import CostTracker
from datronis_relay.domain.ids import UserId
from datronis_relay.domain.pricing import ModelPricing
from tests.conftest import FakeCostStore


@pytest.fixture
def tracker() -> tuple[CostTracker, FakeCostStore]:
    store = FakeCostStore()
    pricing = {
        "claude-sonnet-4-6": ModelPricing(
            input_usd_per_mtok=3.0,
            output_usd_per_mtok=15.0,
        ),
        "claude-opus-4-6": ModelPricing(
            input_usd_per_mtok=15.0,
            output_usd_per_mtok=75.0,
        ),
    }
    return CostTracker(
        store=store, pricing=pricing, default_model="claude-sonnet-4-6"
    ), store


class TestCostTracker:
    async def test_input_only_cost(
        self, tracker: tuple[CostTracker, FakeCostStore]
    ) -> None:
        t, store = tracker
        usage = await t.record(UserId("u1"), tokens_in=1_000_000, tokens_out=0)
        assert usage.tokens_in == 1_000_000
        assert usage.tokens_out == 0
        assert usage.cost_usd == pytest.approx(3.0)
        assert len(store.records) == 1
        assert store.records[0][:3] == (UserId("u1"), 1_000_000, 0)
        assert store.records[0][3] == pytest.approx(3.0)

    async def test_combined_input_and_output_cost(
        self, tracker: tuple[CostTracker, FakeCostStore]
    ) -> None:
        t, _ = tracker
        # 500k * 3/M + 200k * 15/M = 1.5 + 3.0 = 4.5
        usage = await t.record(
            UserId("u1"), tokens_in=500_000, tokens_out=200_000
        )
        assert usage.cost_usd == pytest.approx(4.5)

    async def test_explicit_model_override(
        self, tracker: tuple[CostTracker, FakeCostStore]
    ) -> None:
        t, _ = tracker
        # Using opus pricing: 1M in = $15, 1M out = $75
        usage = await t.record(
            UserId("u1"),
            tokens_in=1_000_000,
            tokens_out=1_000_000,
            model="claude-opus-4-6",
        )
        assert usage.cost_usd == pytest.approx(90.0)

    async def test_unknown_model_records_zero_cost(
        self, tracker: tuple[CostTracker, FakeCostStore]
    ) -> None:
        t, store = tracker
        usage = await t.record(
            UserId("u1"), tokens_in=1000, tokens_out=1000, model="unknown"
        )
        assert usage.cost_usd == 0.0
        assert store.records[-1][3] == 0.0

    async def test_summary_delegates_to_store(
        self, tracker: tuple[CostTracker, FakeCostStore]
    ) -> None:
        t, _ = tracker
        await t.record(UserId("u1"), tokens_in=100, tokens_out=200)
        await t.record(UserId("u1"), tokens_in=50, tokens_out=100)
        summary = await t.summary(UserId("u1"))
        assert summary.today_tokens_in == 150
        assert summary.today_tokens_out == 300
