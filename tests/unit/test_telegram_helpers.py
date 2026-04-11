"""Unit tests for the pure helpers and the constructor in
`adapters/telegram/bot.py`. No real network calls — the Telegram SDK
is instantiated with a format-valid but obviously fake token."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from datronis_relay.adapters.telegram.bot import (
    TelegramAdapter,
    _guess_mime,
    _to_platform_message,
)
from datronis_relay.core.message_pipeline import MessagePipeline
from datronis_relay.domain.messages import Platform


class _FakePipeline(MessagePipeline):
    def __init__(self) -> None:  # bypass real init
        pass  # type: ignore[override]


class TestGuessMime:
    @pytest.mark.parametrize(
        "filename,expected_prefix",
        [
            ("report.pdf", "application/pdf"),
            ("notes.txt", "text/plain"),
            ("photo.png", "image/png"),
            ("photo.jpg", "image/jpeg"),
            ("archive.tar.gz", "application/"),  # some gzip variant
        ],
    )
    def test_known_extensions(self, filename: str, expected_prefix: str) -> None:
        guess = _guess_mime(filename)
        assert guess.startswith(expected_prefix)

    def test_unknown_extension_falls_back_to_octet_stream(self) -> None:
        assert _guess_mime("mystery.wtf") == "application/octet-stream"

    def test_no_extension_falls_back_to_octet_stream(self) -> None:
        assert _guess_mime("no-extension") == "application/octet-stream"


class TestToPlatformMessage:
    def _fake_update(
        self,
        *,
        user_id: int = 42,
        chat_id: int = 100,
        text: str | None = "hello",
        caption: str | None = None,
        has_message: bool = True,
        has_user: bool = True,
        has_chat: bool = True,
    ) -> SimpleNamespace:
        message = None
        if has_message:
            message = SimpleNamespace(text=text, caption=caption)
        user = SimpleNamespace(id=user_id) if has_user else None
        chat = SimpleNamespace(id=chat_id) if has_chat else None
        return SimpleNamespace(message=message, effective_user=user, effective_chat=chat)

    def test_happy_path(self) -> None:
        update = self._fake_update(text="hi there")
        msg = _to_platform_message(update, ())  # type: ignore[arg-type]
        assert msg is not None
        assert msg.text == "hi there"
        assert msg.user_id == "telegram:42"
        assert msg.platform is Platform.TELEGRAM
        assert msg.channel_ref == "100"

    def test_returns_none_without_message(self) -> None:
        update = self._fake_update(has_message=False)
        assert _to_platform_message(update, ()) is None  # type: ignore[arg-type]

    def test_returns_none_without_user(self) -> None:
        update = self._fake_update(has_user=False)
        assert _to_platform_message(update, ()) is None  # type: ignore[arg-type]

    def test_returns_none_without_chat(self) -> None:
        update = self._fake_update(has_chat=False)
        assert _to_platform_message(update, ()) is None  # type: ignore[arg-type]

    def test_uses_caption_when_text_is_none(self) -> None:
        update = self._fake_update(text=None, caption="photo caption")
        msg = _to_platform_message(update, ())  # type: ignore[arg-type]
        assert msg is not None
        assert msg.text == "photo caption"

    def test_empty_message_without_attachments_is_dropped(self) -> None:
        update = self._fake_update(text="", caption=None)
        assert _to_platform_message(update, ()) is None  # type: ignore[arg-type]


class TestAdapterConstruction:
    def test_init_with_fake_token(self, tmp_path: Path) -> None:
        """TelegramAdapter.__init__ only builds a PTB Application — no
        network call is made until run_forever() is invoked."""
        adapter = TelegramAdapter(
            token="123456:fake-token-not-validated-at-build-time",
            pipeline=_FakePipeline(),
            attachments_temp_dir=str(tmp_path),
            max_attachment_bytes=1024,
        )
        assert adapter._temp_dir == tmp_path
        assert adapter._max_bytes == 1024

    def test_build_reply_channel_with_valid_ref(self, tmp_path: Path) -> None:
        adapter = TelegramAdapter(
            token="123456:fake",
            pipeline=_FakePipeline(),
            attachments_temp_dir=str(tmp_path),
        )
        channel = adapter.build_reply_channel("999")
        assert channel.max_message_length > 0

    def test_build_reply_channel_rejects_non_numeric_ref(self, tmp_path: Path) -> None:
        adapter = TelegramAdapter(
            token="123456:fake",
            pipeline=_FakePipeline(),
            attachments_temp_dir=str(tmp_path),
        )
        with pytest.raises(ValueError, match="invalid telegram channel_ref"):
            adapter.build_reply_channel("not-a-number")
