"""Telegram-specific formatter.

Phase M-1 delivery:

  * `TelegramHtmlFormatter` — implements `MessageFormatter`. Parses
    markdown, renders to Telegram's `parse_mode=HTML` subset, chunks at
    `max_chars`.
  * `render_telegram_html` — pure AST → list[RenderedBlock] converter.
    Exposed so it can be unit-tested in isolation without going through
    `format()`.
  * `LANG_WHITELIST` — the set of language hints Telegram accepts on
    ``<pre><code class="language-...">`` blocks.
"""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.telegram.formatter import (
    TelegramHtmlFormatter,
)
from datronis_relay.infrastructure.formatting.telegram.renderer import (
    LANG_WHITELIST,
    render_telegram_html,
)

__all__ = ["LANG_WHITELIST", "TelegramHtmlFormatter", "render_telegram_html"]
