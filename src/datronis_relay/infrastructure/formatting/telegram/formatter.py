"""`TelegramHtmlFormatter` — the production `MessageFormatter` for Telegram.

Pipeline:

    raw text
      -> markdown_ast.parse()       (mistune -> AST)
      -> render_telegram_html()     (AST -> list[RenderedBlock])
      -> _split_oversized_blocks()  (Phase M-3: re-wrap code blocks that
                                     exceed max_chars with (part i/n) labels)
      -> chunk_blocks()             (packed, length-bounded HTML chunks)

Parse-failure fallback: strip_markdown + escape + chunk.
"""

from __future__ import annotations

import structlog

from datronis_relay.core.chunking import chunk_message
from datronis_relay.infrastructure.formatting.chunker import RenderedBlock, chunk_blocks
from datronis_relay.infrastructure.formatting.code_split import split_code_block
from datronis_relay.infrastructure.formatting.escaping import escape_telegram_html
from datronis_relay.infrastructure.formatting.markdown_ast import parse
from datronis_relay.infrastructure.formatting.metrics import (
    FORMATTER_CHUNKS,
    FORMATTER_FALLBACK,
    FORMATTER_OK,
)
from datronis_relay.infrastructure.formatting.strip_markdown import strip_markdown
from datronis_relay.infrastructure.formatting.telegram.renderer import (
    render_telegram_html,
)

log = structlog.get_logger(__name__)

# Prefix/suffix patterns that identify a Telegram HTML code block.
_PRE_OPEN = "<pre>"
_PRE_CLOSE = "</pre>"
_PRE_CODE_PREFIX = '<pre><code class="language-'


class TelegramHtmlFormatter:
    """Format a Claude response as Telegram-HTML chunks."""

    _PLATFORM = "telegram"

    def format(self, text: str, max_chars: int) -> list[str]:
        if not text or not text.strip():
            return []
        try:
            tokens = parse(text)
            blocks = render_telegram_html(tokens)
            blocks = _split_oversized_blocks(blocks, max_chars)
            chunks = chunk_blocks(blocks, max_chars=max_chars)
        except Exception as exc:  # pragma: no cover
            log.warning(
                "telegram_formatter.parse_failed",
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
    """Post-process: split any code block that exceeds max_chars.

    Non-code blocks and blocks that fit are passed through unchanged.
    Code blocks are detected by their ``<pre>`` / ``<pre><code ...>``
    wrapper and split via ``split_code_block`` with platform-specific
    re-wrapping.
    """
    result: list[RenderedBlock] = []
    for block in blocks:
        if len(block.text) <= max_chars or block.splittable:
            result.append(block)
            continue
        # Check if this is a code block we can split.
        if block.text.startswith(_PRE_OPEN) and block.text.endswith(_PRE_CLOSE):
            result.extend(_split_telegram_pre(block.text, max_chars))
        else:
            result.append(block)
    return result


def _split_telegram_pre(html: str, max_chars: int) -> list[RenderedBlock]:
    """Split a ``<pre>...</pre>`` block at line boundaries."""
    # Detect whether this is <pre><code class="language-X">...</code></pre>
    # or plain <pre>...</pre>.
    if html.startswith(_PRE_CODE_PREFIX):
        # Extract: <pre><code class="language-X">CONTENT</code></pre>
        code_close = "</code></pre>"
        inner_start = html.index(">", html.index(">") + 1) + 1
        inner_end = html.rindex(code_close)
        inner = html[inner_start:inner_end]
        prefix = html[:inner_start]
        suffix = code_close

        def wrap(code: str, label: str) -> str:
            lbl = f" {label}" if label else ""
            return f"{prefix}{code}{lbl}{suffix}"
    else:
        # Plain <pre>CONTENT</pre>
        inner = html[len(_PRE_OPEN) : -len(_PRE_CLOSE)]

        def wrap(code: str, label: str) -> str:
            lbl = f" {label}" if label else ""
            return f"{_PRE_OPEN}{code}{lbl}{_PRE_CLOSE}"

    return split_code_block(inner, max_chars, wrap)


def _fallback_chunks(text: str, max_chars: int) -> list[str]:
    """Strip markdown syntax, escape, and chunk naively."""
    stripped = strip_markdown(text)
    escaped = escape_telegram_html(stripped)
    return chunk_message(escaped, limit=max_chars)
