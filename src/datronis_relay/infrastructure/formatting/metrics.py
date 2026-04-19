"""Prometheus metrics for message formatting.

Three counters track per-platform outcomes:

  * ``message_formatter_ok_total{platform}``       — happy-path render
  * ``message_formatter_fallback_total{platform}``  — parse/render failed,
    strip_markdown fallback used
  * ``message_formatter_error_total{platform}``     — even the fallback
    threw (should never happen in practice)

One histogram tracks how many chunks each format() call produces:

  * ``message_formatter_chunks{platform}`` — bucket distribution of
    chunk counts per response

All metrics are created eagerly on module import so they're registered
with the default Prometheus registry before the first message arrives.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

FORMATTER_OK = Counter(
    "message_formatter_ok_total",
    "Format calls that completed through the normal render path.",
    ["platform"],
)

FORMATTER_FALLBACK = Counter(
    "message_formatter_fallback_total",
    "Format calls where parse/render failed and the strip_markdown fallback was used.",
    ["platform"],
)

FORMATTER_ERROR = Counter(
    "message_formatter_error_total",
    "Format calls where even the fallback failed (should be zero).",
    ["platform"],
)

FORMATTER_CHUNKS = Histogram(
    "message_formatter_chunks",
    "Number of chunks produced per format() call.",
    ["platform"],
    buckets=(1, 2, 3, 5, 8, 10, 15, 20),
)
