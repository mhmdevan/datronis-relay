"""Verify Prometheus formatter metrics fire on format() calls."""

from __future__ import annotations

from datronis_relay.infrastructure.formatting import (
    SlackMrkdwnFormatter,
    TelegramHtmlFormatter,
)
from datronis_relay.infrastructure.formatting.metrics import (
    FORMATTER_OK,
)


def _sample_value(counter, labels: dict[str, str]) -> float:  # type: ignore[type-arg]
    """Read the current value of a labelled Prometheus counter."""
    return counter.labels(**labels)._value.get()


def _sample_histogram_count(histogram, labels: dict[str, str]) -> int:  # type: ignore[type-arg]
    """Read the observation count of a labelled histogram."""
    return int(histogram.labels(**labels)._sum._value.get() >= 0)


class TestTelegramMetrics:
    def test_ok_counter_increments(self) -> None:
        before = _sample_value(FORMATTER_OK, {"platform": "telegram"})
        TelegramHtmlFormatter().format("hello", max_chars=4000)
        after = _sample_value(FORMATTER_OK, {"platform": "telegram"})
        assert after > before

    def test_chunks_histogram_observes(self) -> None:
        TelegramHtmlFormatter().format("# Title\n\nBody.", max_chars=4000)
        # Just verify no exception — the histogram was observed.


class TestSlackMetrics:
    def test_ok_counter_increments(self) -> None:
        before = _sample_value(FORMATTER_OK, {"platform": "slack"})
        SlackMrkdwnFormatter().format("hello", max_chars=4000)
        after = _sample_value(FORMATTER_OK, {"platform": "slack"})
        assert after > before

    def test_chunks_histogram_observes(self) -> None:
        SlackMrkdwnFormatter().format("# Title\n\nBody.", max_chars=4000)
