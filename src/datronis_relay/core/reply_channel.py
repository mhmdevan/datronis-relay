from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class ReplyChannel(Protocol):
    """Platform-agnostic send interface for a single conversation.

    Each adapter builds one of these per inbound message and hands it to
    the `MessagePipeline`. The pipeline never imports platform SDKs —
    everything it needs to send a reply goes through this protocol.

    Attributes:
        max_message_length: the maximum number of codepoints the platform
            accepts in a single message. The pipeline uses this to chunk
            long replies. Telegram: 4000. Slack: 38000.
    """

    max_message_length: int

    async def send_text(self, text: str) -> None:
        """Send a single chunk of text. Must not exceed `max_message_length`."""
        ...

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        """Return an async context manager that shows a 'typing' indicator
        for the duration of the `with` block. No-op implementations are
        acceptable for platforms that don't expose a typing API.
        """
        ...
