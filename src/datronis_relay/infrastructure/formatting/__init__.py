"""Platform-specific message formatting.

Phase M-0 (Foundation) exposes only the scaffolding + `PassthroughFormatter`
as the production default — no markup transformation, just chunking. Phases
M-1 and M-2 will add `TelegramHtmlFormatter` and `SlackMrkdwnFormatter`
against the `MessageFormatter` Protocol in `core.ports`.

Supporting modules (`escaping`, `chunker`, `markdown_ast`) are already in
place so M-1 can land as a pure-addition PR without touching this package
layout.
"""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.passthrough import PassthroughFormatter
from datronis_relay.infrastructure.formatting.slack import SlackMrkdwnFormatter
from datronis_relay.infrastructure.formatting.telegram import TelegramHtmlFormatter

__all__ = ["PassthroughFormatter", "SlackMrkdwnFormatter", "TelegramHtmlFormatter"]
