from __future__ import annotations

import mimetypes
import re
import uuid
from pathlib import Path
from typing import Any

import aiohttp
import structlog
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from datronis_relay.adapters.slack.reply_channel import (
    SlackChannelReplyChannel,
    SlackReplyChannel,
)
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.core.reply_channel import ReplyChannel
from datronis_relay.domain.attachments import FileAttachment
from datronis_relay.domain.ids import UserId, new_correlation_id
from datronis_relay.domain.messages import MessageKind, Platform, PlatformMessage

log = structlog.get_logger(__name__)

_MENTION_PREFIX = re.compile(r"^<@[UW][A-Z0-9]+>\s*")


class SlackAdapter:
    """Slack adapter using Bolt Socket Mode.

    Phase 4 additions:
      - Downloads any files attached to incoming events and threads
        them through the pipeline as `FileAttachment`s.
      - Implements `build_reply_channel(channel_ref)` so the scheduler
        can fire tasks to arbitrary Slack channels.
    """

    def __init__(
        self,
        bot_token: str,
        app_token: str,
        pipeline: MessagePipeline,
        attachments_temp_dir: str | Path = "./data/attachments",
        max_attachment_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self._pipeline = pipeline
        self._temp_dir = Path(attachments_temp_dir)
        self._max_bytes = max_attachment_bytes
        self._temp_dir.mkdir(parents=True, exist_ok=True)

        self._app = AsyncApp(token=bot_token)
        self._handler = AsyncSocketModeHandler(self._app, app_token)
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self._app.event("message")
        async def _on_message(event: dict[str, Any], say: Any) -> None:
            await self._handle_event(event, say)

        @self._app.event("app_mention")
        async def _on_mention(event: dict[str, Any], say: Any) -> None:
            await self._handle_event(event, say)

    async def run_forever(self) -> None:
        log.info("slack.adapter.start")
        try:
            await self._handler.start_async()
        finally:
            await self._handler.close_async()
            log.info("slack.adapter.stop")

    def build_reply_channel(self, channel_ref: str) -> ReplyChannel:
        if not channel_ref:
            raise ValueError("slack channel_ref cannot be empty")
        return SlackChannelReplyChannel(
            client=self._app.client, channel_id=channel_ref
        )

    async def _handle_event(self, event: dict[str, Any], say: Any) -> None:
        if _is_bot_event(event):
            return
        user_id = event.get("user")
        if not user_id:
            return

        text = _strip_mention(event.get("text", "") or "").strip()
        attachments = await self._download_event_files(event)
        if not text and not attachments:
            return

        channel_id = event.get("channel") or ""
        platform_message = PlatformMessage(
            correlation_id=new_correlation_id(),
            platform=Platform.SLACK,
            user_id=UserId(f"{Platform.SLACK.value}:{user_id}"),
            text=text,
            kind=MessageKind.TEXT,
            attachments=attachments,
            channel_ref=channel_id,
        )

        reply_channel = SlackReplyChannel(say)
        await self._pipeline.process(platform_message, reply_channel)

    async def _download_event_files(
        self, event: dict[str, Any]
    ) -> tuple[FileAttachment, ...]:
        files = event.get("files") or []
        if not isinstance(files, list) or not files:
            return ()
        downloads: list[FileAttachment] = []
        for file_info in files:
            if not isinstance(file_info, dict):
                continue
            att = await self._download_file(file_info)
            if att is not None:
                downloads.append(att)
        return tuple(downloads)

    async def _download_file(
        self, file_info: dict[str, Any]
    ) -> FileAttachment | None:
        size = int(file_info.get("size") or 0)
        if size and size > self._max_bytes:
            log.warning(
                "slack.attachment.too_large",
                filename=file_info.get("name"),
                size=size,
                max_bytes=self._max_bytes,
            )
            return None
        url = file_info.get("url_private_download") or file_info.get("url_private")
        if not url:
            return None
        filename = str(file_info.get("name") or f"{uuid.uuid4().hex}.bin")
        mime_type = str(file_info.get("mimetype") or _guess_mime(filename))

        unique = uuid.uuid4().hex[:12]
        safe_name = Path(filename).name
        dest = self._temp_dir / f"{unique}-{safe_name}"

        # Download the file with an authed GET. Slack's `url_private` /
        # `url_private_download` require the bot token as a Bearer header.
        # aiohttp is already a transitive dep of slack-bolt, so no new
        # direct dependency is introduced.
        bot_token = self._app.client.token
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Authorization": f"Bearer {bot_token}"},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        log.warning(
                            "slack.attachment.download_failed",
                            status=response.status,
                            filename=filename,
                        )
                        return None
                    data = await response.read()
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "slack.attachment.download_error",
                error=str(exc),
                filename=filename,
            )
            return None

        if len(data) > self._max_bytes:
            log.warning(
                "slack.attachment.too_large_post_download",
                filename=filename,
                size=len(data),
            )
            return None

        dest.write_bytes(data)
        return FileAttachment(
            path=dest,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )


# ------------------------------------------------------------------------- pure helpers


def _event_to_platform_message(event: dict[str, Any]) -> PlatformMessage | None:
    """Pure variant used by unit tests — no downloads, no attachments.

    Kept for backwards compatibility with Phase 3 tests that cover the
    text-only event path.
    """
    if _is_bot_event(event):
        return None
    user_id = event.get("user")
    if not user_id:
        return None
    text = _strip_mention(event.get("text", "") or "").strip()
    if not text:
        return None
    return PlatformMessage(
        correlation_id=new_correlation_id(),
        platform=Platform.SLACK,
        user_id=UserId(f"{Platform.SLACK.value}:{user_id}"),
        text=text,
        kind=MessageKind.TEXT,
        channel_ref=str(event.get("channel") or ""),
    )


def _is_bot_event(event: dict[str, Any]) -> bool:
    if event.get("bot_id"):
        return True
    subtype = event.get("subtype")
    if isinstance(subtype, str) and subtype in ("bot_message", "message_changed"):
        return True
    return False


def _strip_mention(text: str) -> str:
    return _MENTION_PREFIX.sub("", text, count=1)


def _guess_mime(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"
