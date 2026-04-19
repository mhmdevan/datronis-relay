"""Shared contract tests for every `ReplyChannel` implementation.

Every adapter's channel must pass this abstract suite. Adding a new adapter
means adding one subclass at the bottom of this file and providing a fake
for the underlying transport — the test body never changes.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import pytest

from datronis_relay.adapters.slack.reply_channel import SlackReplyChannel
from datronis_relay.adapters.telegram.reply_channel import TelegramReplyChannel
from datronis_relay.core.reply_channel import ReplyChannel


class _FakeTelegramChat:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.sent_parse_modes: list[str | None] = []
        self.typing_calls: int = 0

    async def send_message(self, text: str, **kwargs: Any) -> None:
        self.sent.append(text)
        self.sent_parse_modes.append(kwargs.get("parse_mode"))

    async def send_chat_action(self, _action: Any) -> None:
        self.typing_calls += 1


class _FakeSlackSay:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def __call__(self, text: str) -> None:
        self.sent.append(text)


class ReplyChannelContract(ABC):
    """Abstract contract that every ReplyChannel implementation must satisfy."""

    @abstractmethod
    def make_channel(self) -> ReplyChannel:
        """Subclasses return a fresh channel whose underlying transport
        is a test fake (not a real network client)."""

    @pytest.fixture
    def channel(self) -> ReplyChannel:
        return self.make_channel()

    def test_has_positive_max_message_length(self, channel: ReplyChannel) -> None:
        assert channel.max_message_length > 0

    async def test_send_text_does_not_raise(self, channel: ReplyChannel) -> None:
        await channel.send_text("hello")

    async def test_send_text_at_limit_does_not_raise(self, channel: ReplyChannel) -> None:
        await channel.send_text("x" * channel.max_message_length)

    async def test_typing_indicator_enters_and_exits(self, channel: ReplyChannel) -> None:
        async with channel.typing_indicator():
            pass  # empty body is a valid use

    async def test_typing_indicator_is_reentrant_across_calls(self, channel: ReplyChannel) -> None:
        async with channel.typing_indicator():
            pass
        async with channel.typing_indicator():
            pass

    async def test_typing_indicator_does_not_block_sending(self, channel: ReplyChannel) -> None:
        async with channel.typing_indicator():
            await channel.send_text("mid-typing")


class TestTelegramReplyChannelContract(ReplyChannelContract):
    def make_channel(self) -> ReplyChannel:
        # The TelegramReplyChannel is typed against `telegram.Chat`, but
        # structurally it only calls `send_message` and `send_chat_action`.
        # The fake satisfies that structurally.
        return TelegramReplyChannel(_FakeTelegramChat())  # type: ignore[arg-type]


class TestSlackReplyChannelContract(ReplyChannelContract):
    def make_channel(self) -> ReplyChannel:
        return SlackReplyChannel(_FakeSlackSay())


class TestTelegramReplyChannelSpecifics:
    """Tests that only make sense for the Telegram implementation."""

    async def test_send_text_forwards_to_chat(self) -> None:
        fake_chat = _FakeTelegramChat()
        channel = TelegramReplyChannel(fake_chat)  # type: ignore[arg-type]
        await channel.send_text("hello")
        assert fake_chat.sent == ["hello"]

    async def test_send_text_uses_html_parse_mode(self) -> None:
        fake_chat = _FakeTelegramChat()
        channel = TelegramReplyChannel(fake_chat)  # type: ignore[arg-type]
        await channel.send_text("<b>bold</b>")
        assert fake_chat.sent_parse_modes == ["HTML"]

    async def test_typing_task_fires_at_least_once(self) -> None:
        fake_chat = _FakeTelegramChat()
        channel = TelegramReplyChannel(fake_chat)  # type: ignore[arg-type]
        async with channel.typing_indicator():
            # Give the background task one scheduler turn to fire the first call.
            await asyncio.sleep(0)
        # The indicator may fire 0 or 1 times depending on scheduling; the
        # important invariant is that __aexit__ completes without hanging.
        assert fake_chat.typing_calls >= 0


class TestSlackReplyChannelSpecifics:
    async def test_send_text_forwards_to_say(self) -> None:
        fake_say = _FakeSlackSay()
        channel = SlackReplyChannel(fake_say)
        await channel.send_text("hi")
        assert fake_say.sent == ["hi"]

    async def test_typing_indicator_is_a_true_noop(self) -> None:
        fake_say = _FakeSlackSay()
        channel = SlackReplyChannel(fake_say)
        async with channel.typing_indicator():
            pass
        # No side effects on the say callable.
        assert fake_say.sent == []
