from __future__ import annotations

from contextlib import AbstractAsyncContextManager, AsyncExitStack
from types import TracebackType
from typing import Any

from slack_sdk.web.async_client import AsyncWebClient

from datronis_relay.core.reply_channel import ReplyChannel

# Slack's per-message limit is ~40,000 chars. Leave margin for the continuation
# marker and any future per-channel prefixes.
SLACK_MAX_MESSAGE_LENGTH = 38000


class SlackReplyChannel(ReplyChannel):
    """ReplyChannel backed by a Slack Bolt `say` function.

    `say` is the Bolt-provided callable that posts a message to the channel
    the event came from. We accept it as an `Any` because the type shape
    varies between sync and async Bolt handlers and we never introspect it.
    """

    max_message_length: int = SLACK_MAX_MESSAGE_LENGTH

    def __init__(self, say: Any) -> None:
        self._say = say

    async def send_text(self, text: str) -> None:
        await self._say(text)

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        # Slack's Socket-Mode API doesn't expose a first-class typing
        # indicator the way Telegram does. Posting "🤔 thinking..." and
        # editing it later works but introduces UX noise. v0.3 uses a
        # no-op — the user will see the final reply as soon as it's ready.
        return _NoopTypingIndicator()


class _NoopTypingIndicator(AbstractAsyncContextManager[None]):
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


class SlackChannelReplyChannel(ReplyChannel):
    """ReplyChannel that sends via the Slack Web API using a channel id.

    Used for scheduled tasks where we don't have a Bolt `say` callable,
    only a stored channel id. Constructed from the adapter's own
    `AsyncWebClient` so it shares auth with the main event loop.
    """

    max_message_length: int = SLACK_MAX_MESSAGE_LENGTH

    def __init__(self, client: AsyncWebClient, channel_id: str) -> None:
        self._client = client
        self._channel_id = channel_id

    async def send_text(self, text: str) -> None:
        await self._client.chat_postMessage(channel=self._channel_id, text=text)

    def typing_indicator(self) -> AbstractAsyncContextManager[None]:
        return _NoopTypingIndicator()


# Re-export in case callers want to compose no-op context managers.
__all__ = [
    "SlackReplyChannel",
    "SlackChannelReplyChannel",
    "SLACK_MAX_MESSAGE_LENGTH",
    "AsyncExitStack",
]
