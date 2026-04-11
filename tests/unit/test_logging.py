"""Tests for `infrastructure/logging.py`."""

from __future__ import annotations

import structlog

from datronis_relay.domain.ids import CorrelationId
from datronis_relay.infrastructure.logging import (
    bind_correlation,
    clear_correlation,
    configure_logging,
)


class TestConfigureLogging:
    def test_json_mode(self) -> None:
        configure_logging(level="INFO", json_output=True)
        # Must not raise; structlog is configured
        logger = structlog.get_logger("test")
        logger.info("hello", key="value")  # smoke

    def test_console_mode(self) -> None:
        configure_logging(level="DEBUG", json_output=False)
        logger = structlog.get_logger("test")
        logger.info("hello", key="value")

    def test_levels_are_case_insensitive(self) -> None:
        configure_logging(level="info", json_output=True)
        configure_logging(level="WARNING", json_output=True)
        configure_logging(level="Error", json_output=False)


class TestCorrelationBinding:
    def test_bind_then_clear(self) -> None:
        bind_correlation(CorrelationId("test-corr-id"))
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("correlation_id") == "test-corr-id"

        clear_correlation()
        ctx = structlog.contextvars.get_contextvars()
        assert "correlation_id" not in ctx

    def test_bind_overwrites_prior_value(self) -> None:
        bind_correlation(CorrelationId("first"))
        bind_correlation(CorrelationId("second"))
        ctx = structlog.contextvars.get_contextvars()
        assert ctx.get("correlation_id") == "second"
        clear_correlation()

    def test_clear_on_empty_is_a_noop(self) -> None:
        clear_correlation()  # no prior bind; must not raise
        clear_correlation()  # idempotent
