from __future__ import annotations

from typing import Any

from datronis_relay.adapters.slack.bot import (
    _event_to_platform_message,
    _is_bot_event,
    _strip_mention,
)
from datronis_relay.domain.messages import Platform


class TestStripMention:
    def test_no_mention_is_passthrough(self) -> None:
        assert _strip_mention("hello") == "hello"

    def test_leading_user_mention_is_removed(self) -> None:
        assert _strip_mention("<@U12345> hello") == "hello"

    def test_leading_workspace_mention_is_removed(self) -> None:
        assert _strip_mention("<@W9999> hi there") == "hi there"

    def test_mention_with_no_space_is_removed(self) -> None:
        assert _strip_mention("<@U12345>hello") == "hello"

    def test_mention_in_middle_is_kept(self) -> None:
        assert _strip_mention("hey <@U12345> how are you") == "hey <@U12345> how are you"

    def test_empty_input(self) -> None:
        assert _strip_mention("") == ""


class TestIsBotEvent:
    def test_event_with_bot_id_is_bot(self) -> None:
        assert _is_bot_event({"bot_id": "B0123"}) is True

    def test_event_with_bot_message_subtype_is_bot(self) -> None:
        assert _is_bot_event({"subtype": "bot_message"}) is True

    def test_event_with_message_changed_subtype_is_bot(self) -> None:
        assert _is_bot_event({"subtype": "message_changed"}) is True

    def test_normal_user_event_is_not_bot(self) -> None:
        assert _is_bot_event({"user": "U123", "text": "hi"}) is False


class TestEventToPlatformMessage:
    def _event(self, **overrides: Any) -> dict[str, Any]:
        base: dict[str, Any] = {
            "user": "U12345",
            "text": "what time is it",
            "channel": "C99999",
        }
        base.update(overrides)
        return base

    def test_happy_path(self) -> None:
        msg = _event_to_platform_message(self._event())
        assert msg is not None
        assert msg.platform is Platform.SLACK
        assert msg.user_id == "slack:U12345"
        assert msg.text == "what time is it"
        assert msg.correlation_id  # non-empty

    def test_bot_event_is_dropped(self) -> None:
        assert _event_to_platform_message(self._event(bot_id="B1")) is None

    def test_subtype_bot_message_is_dropped(self) -> None:
        assert _event_to_platform_message(self._event(subtype="bot_message")) is None

    def test_missing_user_is_dropped(self) -> None:
        event = self._event()
        del event["user"]
        assert _event_to_platform_message(event) is None

    def test_empty_text_after_mention_strip_is_dropped(self) -> None:
        assert _event_to_platform_message(self._event(text="<@U12345>   ")) is None

    def test_mention_prefix_is_stripped_from_forwarded_text(self) -> None:
        msg = _event_to_platform_message(self._event(text="<@U12345> restart nginx"))
        assert msg is not None
        assert msg.text == "restart nginx"

    def test_user_id_is_namespaced(self) -> None:
        msg = _event_to_platform_message(self._event(user="UABCDEF"))
        assert msg is not None
        assert msg.user_id == "slack:UABCDEF"

    def test_cross_platform_ids_do_not_collide(self) -> None:
        """A Slack user id 12345 must not collide with Telegram user id 12345."""
        msg = _event_to_platform_message(self._event(user="12345"))
        assert msg is not None
        assert msg.user_id == "slack:12345"
        assert msg.user_id != "telegram:12345"
