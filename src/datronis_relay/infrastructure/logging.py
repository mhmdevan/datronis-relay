from __future__ import annotations

import logging
import sys

import structlog

from datronis_relay.domain.ids import CorrelationId


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog + stdlib logging to a single stdout stream.

    JSON is the default for production. Set `DATRONIS_LOG_JSON=false` in the
    env for a human-readable console view during development.
    """
    log_level = logging.getLevelName(level.upper())

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def bind_correlation(correlation_id: CorrelationId) -> None:
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def clear_correlation() -> None:
    structlog.contextvars.unbind_contextvars("correlation_id")
