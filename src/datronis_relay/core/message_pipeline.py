from __future__ import annotations

from collections.abc import AsyncIterator, Mapping

import structlog

from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.chunking import chunk_message
from datronis_relay.core.command_router import (
    CommandRouter,
    Reply,
    StaticReply,
)
from datronis_relay.core.ports import MessageFormatter
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.domain.errors import RelayError
from datronis_relay.domain.messages import Platform, PlatformMessage
from datronis_relay.infrastructure.logging import bind_correlation, clear_correlation

log = structlog.get_logger(__name__)


class MessagePipeline:
    """Platform-agnostic inbound-message handler.

    This is the single place that knows how to take a `PlatformMessage`,
    authenticate the sender, route the command, and deliver the reply.
    Every adapter (Telegram, Slack, future Discord) reduces to:

        message = <adapter-specific parsing>
        channel = <adapter-specific ReplyChannel>
        await pipeline.process(message, channel)

    By extracting this out of `TelegramAdapter` in Phase 3 we guarantee
    that a second adapter cannot silently drift in behavior.
    """

    def __init__(
        self,
        auth: AuthGuard,
        router: CommandRouter,
        formatter: MessageFormatter | None = None,
        formatters: Mapping[Platform, MessageFormatter] | None = None,
    ) -> None:
        """Initialise the pipeline.

        Args:
            auth: authenticates inbound messages against the allowlist.
            router: dispatches each message to the correct command.
            formatter: fallback formatter used when `formatters` has no
                entry for the inbound message's platform. If both
                `formatter` and `formatters` are omitted, a private
                in-core default preserves pre-Phase-M-0 behaviour.
            formatters: per-platform formatter map. Preferred in
                production (Phase M-1 onward) so Telegram can use
                `TelegramHtmlFormatter` while Slack uses
                `PassthroughFormatter`. Missing platforms fall through
                to `formatter`.

        Clean-Architecture note: neither parameter imports from
        `infrastructure/formatting/` here — they are Protocols. The
        composition root (`main.py`) is the only place that wires up
        concrete formatters.
        """
        self._auth = auth
        self._router = router
        # Platform-specific formatters picked first, fall back to
        # `formatter`, fall back to the in-core default last.
        self._platform_formatters: dict[Platform, MessageFormatter] = dict(
            formatters or {}
        )
        self._default_formatter: MessageFormatter = (
            formatter or _DefaultChunkingFormatter()
        )

    async def process(
        self,
        message: PlatformMessage,
        channel: ReplyChannel,
    ) -> None:
        bind_correlation(message.correlation_id)
        log.info(
            "pipeline.received",
            platform=message.platform.value,
            user_id=message.user_id,
            text_len=len(message.text),
        )
        try:
            user = self._auth.authenticate(message)
            reply = await self._router.dispatch(message, user)
            await self._deliver(channel, message.platform, reply)
        except RelayError as exc:
            log.warning(
                "pipeline.relay_error",
                category=exc.category.value,
                error=str(exc),
            )
            await self._safe_send(channel, message.platform, exc.user_message())
        except Exception as exc:
            log.exception("pipeline.unexpected", error=str(exc))
            await self._safe_send(
                channel,
                message.platform,
                f"[INTERNAL] unexpected error (ref: {message.correlation_id})",
            )
        finally:
            _cleanup_attachments(message)
            clear_correlation()

    # ------------------------------------------------------------------ delivery

    def _pick_formatter(self, platform: Platform) -> MessageFormatter:
        """Return the formatter for `platform`, or the default if unset."""
        return self._platform_formatters.get(platform, self._default_formatter)

    async def _deliver(
        self,
        channel: ReplyChannel,
        platform: Platform,
        reply: Reply,
    ) -> None:
        if isinstance(reply, StaticReply):
            await self._send_chunked(channel, platform, reply.text)
            return
        await self._deliver_stream(channel, platform, reply.chunks)

    async def _deliver_stream(
        self,
        channel: ReplyChannel,
        platform: Platform,
        chunks: AsyncIterator[str],
    ) -> None:
        buffer: list[str] = []
        async with channel.typing_indicator():
            async for piece in chunks:
                buffer.append(piece)

        full_text = "".join(buffer).strip()
        if not full_text:
            await channel.send_text("(claude returned no content)")
            return
        await self._send_chunked(channel, platform, full_text)

    async def _send_chunked(
        self,
        channel: ReplyChannel,
        platform: Platform,
        text: str,
    ) -> None:
        formatter = self._pick_formatter(platform)
        for chunk in formatter.format(text, max_chars=channel.max_message_length):
            await channel.send_text(chunk)

    async def _safe_send(
        self,
        channel: ReplyChannel,
        platform: Platform,
        text: str,
    ) -> None:
        """Like `_send_chunked` but never raises — used in error paths."""
        try:
            await self._send_chunked(channel, platform, text)
        except Exception as exc:
            log.error("pipeline.send_failed", error=str(exc))


class _DefaultChunkingFormatter:
    """Built-in fallback `MessageFormatter` used when none is injected.

    Delegates to `core.chunking.chunk_message` so behaviour is identical
    to the pre-Phase-M-0 code path. This keeps `MessagePipeline` usable
    by unit tests that don't want to pull in `infrastructure/formatting/`
    (Clean-Architecture boundary: core must not import from infrastructure).

    Production wiring lives in `main.py` and passes a real
    `PassthroughFormatter` — this class is never reached on the real
    bot's send path.
    """

    def format(self, text: str, max_chars: int) -> list[str]:
        if not text or not text.strip():
            return []
        return chunk_message(text, limit=max_chars)


def _cleanup_attachments(message: PlatformMessage) -> None:
    """Delete any temp files the adapter downloaded for this message.

    Called in the pipeline's `finally` so files are removed on success,
    user error, rate limit, auth fail, or internal exception. Swallows
    any unlink error — a leaked temp file is acceptable, a crash during
    cleanup is not.
    """
    for attachment in message.attachments:
        try:
            attachment.path.unlink(missing_ok=True)
        except Exception as exc:
            log.warning(
                "pipeline.cleanup_failed",
                path=str(attachment.path),
                error=str(exc),
            )
