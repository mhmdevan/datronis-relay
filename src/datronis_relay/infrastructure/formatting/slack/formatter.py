"""`SlackMrkdwnFormatter` — the production `MessageFormatter` for Slack.

Pipeline:

    raw text -> markdown_ast.parse() -> render_slack_mrkdwn()
      -> _split_oversized_blocks() -> chunk_blocks()

Parse-failure fallback: strip_markdown + escape + chunk.
"""

from __future__ import annotations

import structlog

from datronis_relay.core.chunking import chunk_message
from datronis_relay.infrastructure.formatting.chunker import RenderedBlock, chunk_blocks
from datronis_relay.infrastructure.formatting.code_split import split_code_block
from datronis_relay.infrastructure.formatting.escaping import escape_slack_text
from datronis_relay.infrastructure.formatting.markdown_ast import parse
from datronis_relay.infrastructure.formatting.metrics import (
    FORMATTER_CHUNKS,
    FORMATTER_FALLBACK,
    FORMATTER_OK,
)
from datronis_relay.infrastructure.formatting.slack.renderer import (
    render_slack_mrkdwn,
)
from datronis_relay.infrastructure.formatting.strip_markdown import strip_markdown

log = structlog.get_logger(__name__)

_FENCE = "```"


class SlackMrkdwnFormatter:
    """Format a Claude response as Slack mrkdwn chunks."""

    _PLATFORM = "slack"

    def format(self, text: str, max_chars: int) -> list[str]:
        if not text or not text.strip():
            return []
        try:
            tokens = parse(text)
            blocks = render_slack_mrkdwn(tokens)
            blocks = _split_oversized_blocks(blocks, max_chars)
            chunks = chunk_blocks(blocks, max_chars=max_chars)
        except Exception as exc:  # pragma: no cover
            log.warning(
                "slack_formatter.parse_failed",
                error=str(exc),
                input_preview=text[:200],
            )
            FORMATTER_FALLBACK.labels(platform=self._PLATFORM).inc()
            chunks = _fallback_chunks(text, max_chars=max_chars)
            FORMATTER_CHUNKS.labels(platform=self._PLATFORM).observe(len(chunks))
            return chunks
        FORMATTER_OK.labels(platform=self._PLATFORM).inc()
        FORMATTER_CHUNKS.labels(platform=self._PLATFORM).observe(len(chunks))
        return chunks


def _split_oversized_blocks(
    blocks: list[RenderedBlock], max_chars: int
) -> list[RenderedBlock]:
    """Post-process: split any code fence that exceeds max_chars."""
    result: list[RenderedBlock] = []
    for block in blocks:
        if len(block.text) <= max_chars or block.splittable:
            result.append(block)
            continue
        if block.text.startswith(_FENCE + "\n") and block.text.endswith("\n" + _FENCE):
            result.extend(_split_slack_fence(block.text, max_chars))
        else:
            result.append(block)
    return result


def _split_slack_fence(text: str, max_chars: int) -> list[RenderedBlock]:
    """Split a triple-backtick fenced code block at line boundaries."""
    inner = text[len(_FENCE) + 1 : -(len(_FENCE) + 1)]

    def wrap(code: str, label: str) -> str:
        lbl = f" {label}" if label else ""
        return f"{_FENCE}\n{code}{lbl}\n{_FENCE}"

    return split_code_block(inner, max_chars, wrap)


def _fallback_chunks(text: str, max_chars: int) -> list[str]:
    """Strip markdown syntax, escape, and chunk naively."""
    stripped = strip_markdown(text)
    escaped = escape_slack_text(stripped)
    return chunk_message(escaped, limit=max_chars)
