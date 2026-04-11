from __future__ import annotations

import asyncio
import contextlib
from contextlib import AbstractAsyncContextManager
from types import TracebackType

import structlog
from telegram import Bot, Chat
from telegram.constants import ChatAction

from datronis_relay.core.reply_channel import ReplyChannel

log = structlog.get_logger(__name__)

# Telegram's hard cap is 4096 codepoints. Leave margin for the continuation
# marker and any adapter-level prefixes.
TELEGRAM_MAX_MESSAGE_LENGTH = 4000
TYPING_INTERVAL_SECONDS = 4.0


class TelegramReplyChannel(ReplyChannel):
    """ReplyChannel backed by a single python-telegram-bot `Chat`."""

    max_message_length: int = TELEGRAM_MAX_MESSAGE_LENGTH

    def __init__(self, chat: Chat) -> None:
        self._chat = chat

    async def send_text(self, text: str) -> None:
        await self._chat.send_message(text)

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        return _TelegramTypingIndicator(self._chat)


class _TelegramTypingIndicator(AbstractAsyncContextManager[None]):
    """Runs a background task that sends a typing action every 4 seconds."""

    def __init__(self, chat: Chat) -> None:
        self._chat = chat
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="telegram-typing")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        try:
            while True:
                try:
                    await self._chat.send_chat_action(ChatAction.TYPING)
                except Exception as exc:
                    log.debug("telegram.typing.failed", error=str(exc))
                await asyncio.sleep(TYPING_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return


class TelegramBotReplyChannel(ReplyChannel):
    """ReplyChannel that sends via an explicit bot + chat_id.

    Used for scheduled tasks, where the adapter reconstructs a channel
    from a stored `channel_ref` (the chat id as a string). The normal
    `TelegramReplyChannel` holds a `Chat` object supplied by PTB for
    incoming updates; this one only needs the raw id.
    """

    max_message_length: int = TELEGRAM_MAX_MESSAGE_LENGTH

    def __init__(self, bot: Bot, chat_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id

    async def send_text(self, text: str) -> None:
        await self._bot.send_message(chat_id=self._chat_id, text=text)

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        return _TelegramBotTypingIndicator(self._bot, self._chat_id)


class _TelegramBotTypingIndicator(AbstractAsyncContextManager[None]):
    def __init__(self, bot: Bot, chat_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="telegram-bot-typing")

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _loop(self) -> None:
        try:
            while True:
                try:
                    await self._bot.send_chat_action(
                        chat_id=self._chat_id, action=ChatAction.TYPING
                    )
                except Exception as exc:
                    log.debug("telegram.typing.failed", error=str(exc))
                await asyncio.sleep(TYPING_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return
