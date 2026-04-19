"""Production default formatter for Phase M-0.

`PassthroughFormatter` performs **no** markup transformation. It takes
Claude's raw response text and emits it as chunks via the existing
`core.chunking.chunk_message` helper — identical to the pre-M-0 code
path in `MessagePipeline._send_chunked`.

Why ship it at all if it does nothing? Because it's the *injection
point* that makes Phase M-1 a one-line composition-root change:

    # Phase M-0 (today)
    pipeline = MessagePipeline(..., formatter=PassthroughFormatter())

    # Phase M-1 (Telegram HTML lands)
    pipeline = MessagePipeline(..., formatter=TelegramHtmlFormatter())

No adapter, no pipeline, no call site changes between those two PRs —
only the formatter identity.

Correctness contract: the roadmap mandates "zero production regression"
for M-0. Every byte that leaves the Telegram/Slack API today must be
identical after this PR lands. The identity is guaranteed by delegating
directly to the same `chunk_message` the pipeline used before.
"""

from __future__ import annotations

from datronis_relay.core.chunking import chunk_message


class PassthroughFormatter:
    """Delegates to `chunk_message`. Stateless, thread-safe, trivially testable."""

    def format(self, text: str, max_chars: int) -> list[str]:
        """Return chunks of `text`, each ≤ `max_chars` codepoints.

        Empty / whitespace-only input returns `[]` — there is nothing to
        send, and the pipeline replaces empty replies with an explicit
        "(claude returned no content)" message at a higher level.
        """
        if not text or not text.strip():
            return []
        return chunk_message(text, limit=max_chars)
