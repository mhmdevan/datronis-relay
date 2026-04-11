"""Smoke tests for `infrastructure/metrics.py` — the Prometheus counters
and histogram exist with the correct names and labels."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

from datronis_relay.infrastructure import metrics


class TestMetricObjects:
    def test_messages_total_is_a_counter(self) -> None:
        assert isinstance(metrics.MESSAGES_TOTAL, Counter)

    def test_claude_tokens_total_is_a_counter(self) -> None:
        assert isinstance(metrics.CLAUDE_TOKENS_TOTAL, Counter)

    def test_claude_cost_usd_total_is_a_counter(self) -> None:
        assert isinstance(metrics.CLAUDE_COST_USD_TOTAL, Counter)

    def test_dispatch_duration_seconds_is_a_histogram(self) -> None:
        assert isinstance(metrics.DISPATCH_DURATION_SECONDS, Histogram)

    def test_messages_total_has_outcome_label(self) -> None:
        # Exercising `.labels(outcome="ok")` proves the label name matches.
        labelled = metrics.MESSAGES_TOTAL.labels(outcome="ok")
        labelled.inc()  # must not raise

    def test_claude_tokens_total_has_direction_label(self) -> None:
        metrics.CLAUDE_TOKENS_TOTAL.labels(direction="in").inc(100)
        metrics.CLAUDE_TOKENS_TOTAL.labels(direction="out").inc(200)

    def test_cost_counter_can_be_incremented(self) -> None:
        metrics.CLAUDE_COST_USD_TOTAL.inc(0.001)

    def test_duration_histogram_can_observe(self) -> None:
        metrics.DISPATCH_DURATION_SECONDS.observe(0.25)


class TestStartMetricsServerCallableExists:
    def test_function_is_defined(self) -> None:
        assert callable(metrics.start_metrics_server)
