from __future__ import annotations

from collections.abc import AsyncIterator

import structlog

from datronis_relay.core.auth import AuthGuard
from datronis_relay.core.chunking import chunk_message
from datronis_relay.core.command_router import (
    CommandRouter,
    Reply,
    StaticReply,
    StreamReply,
)
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.domain.errors import RelayError
from datronis_relay.domain.messages import PlatformMessage
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

    def __init__(self, auth: AuthGuard, router: CommandRouter) -> None:
        self._auth = auth
        self._router = router

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
            await self._deliver(channel, reply)
        except RelayError as exc:
            log.warning(
                "pipeline.relay_error",
                category=exc.category.value,
                error=str(exc),
            )
            await self._safe_send(channel, exc.user_message())
        except Exception as exc:  # noqa: BLE001
            log.exception("pipeline.unexpected", error=str(exc))
            await self._safe_send(
                channel,
                f"[INTERNAL] unexpected error (ref: {message.correlation_id})",
            )
        finally:
            _cleanup_attachments(message)
            clear_correlation()

    # ------------------------------------------------------------------ delivery

    async def _deliver(self, channel: ReplyChannel, reply: Reply) -> None:
        if isinstance(reply, StaticReply):
            await self._send_chunked(channel, reply.text)
            return
        await self._deliver_stream(channel, reply.chunks)

    async def _deliver_stream(
        self,
        channel: ReplyChannel,
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
        await self._send_chunked(channel, full_text)

    async def _send_chunked(self, channel: ReplyChannel, text: str) -> None:
        for chunk in chunk_message(text, limit=channel.max_message_length):
            await channel.send_text(chunk)

    async def _safe_send(self, channel: ReplyChannel, text: str) -> None:
        """Like `_send_chunked` but never raises — used in error paths."""
        try:
            await self._send_chunked(channel, text)
        except Exception as exc:  # noqa: BLE001
            log.error("pipeline.send_failed", error=str(exc))


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
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "pipeline.cleanup_failed",
                path=str(attachment.path),
                error=str(exc),
            )
