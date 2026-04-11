from __future__ import annotations

import structlog
from prometheus_client import Counter, Histogram, start_http_server

log = structlog.get_logger(__name__)

MESSAGES_TOTAL = Counter(
    "datronis_messages_total",
    "Total inbound messages processed, labelled by outcome.",
    ["outcome"],  # ok | auth_fail | rate_limited | claude_error | internal_error
)

CLAUDE_TOKENS_TOTAL = Counter(
    "datronis_claude_tokens_total",
    "Total Claude tokens, labelled by direction.",
    ["direction"],  # in | out
)

CLAUDE_COST_USD_TOTAL = Counter(
    "datronis_claude_cost_usd_total",
    "Total Claude cost in USD.",
)

DISPATCH_DURATION_SECONDS = Histogram(
    "datronis_dispatch_duration_seconds",
    "Latency of the full dispatch pipeline, from inbound message to final reply.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)


def start_metrics_server(host: str, port: int) -> None:
    """Start a background HTTP server exposing /metrics in Prometheus format."""
    log.info("metrics.server.start", host=host, port=port)
    start_http_server(port, addr=host)
