from __future__ import annotations

import asyncio
import mimetypes
import uuid
from pathlib import Path

import structlog
from telegram import Document, PhotoSize, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from datronis_relay.adapters.telegram.reply_channel import (
    TelegramBotReplyChannel,
    TelegramReplyChannel,
)
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.domain.attachments import FileAttachment
from datronis_relay.domain.ids import UserId, new_correlation_id
from datronis_relay.domain.messages import MessageKind, Platform, PlatformMessage

log = structlog.get_logger(__name__)

SUPPORTED_COMMANDS = (
    "start",
    "help",
    "status",
    "stop",
    "ask",
    "cost",
    "schedule",
    "schedules",
    "unschedule",
)


class TelegramAdapter:
    """Telegram long-polling adapter.

    Phase 4 additions:
      - Accepts documents and photos as attachments, downloads them to a
        temp dir, and threads the resulting `FileAttachment`s through the
        `PlatformMessage` to the Claude client.
      - Implements `build_reply_channel(channel_ref)` so the scheduler
        can fire tasks to arbitrary chat ids without holding a Chat
        object.
    """

    def __init__(
        self,
        token: str,
        pipeline: MessagePipeline,
        attachments_temp_dir: str | Path = "./data/attachments",
        max_attachment_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._pipeline = pipeline
        self._temp_dir = Path(attachments_temp_dir)
        self._max_bytes = max_attachment_bytes
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        self._app: Application = ApplicationBuilder().token(token).concurrent_updates(True).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        for name in SUPPORTED_COMMANDS:
            self._app.add_handler(CommandHandler(name, self._on_update))
        self._app.add_handler(
            MessageHandler(
                (filters.TEXT | filters.Document.ALL | filters.PHOTO) & ~filters.COMMAND,
                self._on_update,
            )
        )

    async def run_forever(self) -> None:
        log.info("telegram.adapter.start")
        await self._app.initialize()
        await self._app.start()
        assert self._app.updater is not None
        await self._app.updater.start_polling(drop_pending_updates=True)
        try:
            await asyncio.Event().wait()
        finally:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            log.info("telegram.adapter.stop")

    def build_reply_channel(self, channel_ref: str) -> ReplyChannel:
        """Construct a reply channel for out-of-band delivery (scheduler).

        `channel_ref` must be a Telegram chat id as a decimal string.
        """
        try:
            chat_id = int(channel_ref)
        except ValueError as exc:
            raise ValueError(f"invalid telegram channel_ref: {channel_ref!r}") from exc
        return TelegramBotReplyChannel(bot=self._app.bot, chat_id=chat_id)

    # ------------------------------------------------------------------ handlers

    async def _on_update(
        self,
        update: Update,
        _context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if update.message is None or update.effective_chat is None:
            return

        attachments = await self._download_attachments(update)
        message = _to_platform_message(update, attachments)
        if message is None:
            return

        channel = TelegramReplyChannel(update.effective_chat)
        await self._pipeline.process(message, channel)

    async def _download_attachments(self, update: Update) -> tuple[FileAttachment, ...]:
        """Download any documents or photos attached to the message.

        - Documents: saved with their original filename.
        - Photos: Telegram sends multiple resolutions; we pick the largest.
        - Oversized files are skipped with a warning — Claude never sees them.
        """
        assert update.message is not None
        downloads: list[FileAttachment] = []

        if update.message.document is not None:
            att = await self._download_document(update.message.document)
            if att is not None:
                downloads.append(att)

        if update.message.photo:
            largest: PhotoSize = max(update.message.photo, key=lambda p: p.file_size or 0)
            att = await self._download_photo(largest)
            if att is not None:
                downloads.append(att)

        return tuple(downloads)

    async def _download_document(self, document: Document) -> FileAttachment | None:
        if document.file_size and document.file_size > self._max_bytes:
            log.warning(
                "telegram.attachment.too_large",
                filename=document.file_name,
                size=document.file_size,
                max_bytes=self._max_bytes,
            )
            return None
        tg_file = await document.get_file()
        filename = document.file_name or f"{document.file_unique_id}.bin"
        mime_type = document.mime_type or _guess_mime(filename)
        dest = self._alloc_path(filename)
        await tg_file.download_to_drive(str(dest))
        size = dest.stat().st_size
        return FileAttachment(
            path=dest,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size,
        )

    async def _download_photo(self, photo: PhotoSize) -> FileAttachment | None:
        if photo.file_size and photo.file_size > self._max_bytes:
            log.warning(
                "telegram.attachment.too_large",
                kind="photo",
                size=photo.file_size,
                max_bytes=self._max_bytes,
            )
            return None
        tg_file = await photo.get_file()
        filename = f"{photo.file_unique_id}.jpg"
        dest = self._alloc_path(filename)
        await tg_file.download_to_drive(str(dest))
        size = dest.stat().st_size
        return FileAttachment(
            path=dest,
            filename=filename,
            mime_type="image/jpeg",
            size_bytes=size,
        )

    def _alloc_path(self, filename: str) -> Path:
        # Prefix with a short uuid to prevent collisions and to give the
        # pipeline's cleanup step a unique target per message.
        unique = uuid.uuid4().hex[:12]
        safe_name = Path(filename).name  # strip directory traversal
        return self._temp_dir / f"{unique}-{safe_name}"


def _to_platform_message(
    update: Update, attachments: tuple[FileAttachment, ...]
) -> PlatformMessage | None:
    if update.message is None or update.effective_user is None:
        return None
    if update.effective_chat is None:
        return None
    text = update.message.text or update.message.caption or ""
    # Drop completely empty messages that also have no attachments —
    # typical for system events we didn't subscribe to.
    if not text and not attachments:
        return None
    namespaced_id = f"{Platform.TELEGRAM.value}:{update.effective_user.id}"
    return PlatformMessage(
        correlation_id=new_correlation_id(),
        platform=Platform.TELEGRAM,
        user_id=UserId(namespaced_id),
        text=text,
        kind=MessageKind.TEXT,
        attachments=attachments,
        channel_ref=str(update.effective_chat.id),
    )


def _guess_mime(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
