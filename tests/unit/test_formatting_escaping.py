"""Unit tests for the pure escape helpers used by every platform renderer."""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.escaping import (
    escape_slack_text,
    escape_slack_url,
    escape_telegram_attr,
    escape_telegram_html,
)


class TestEscapeTelegramHtml:
    def test_escapes_angle_brackets_and_ampersand(self) -> None:
        assert escape_telegram_html("<a>&") == "&lt;a&gt;&amp;"

    def test_leaves_quotes_untouched_in_body_text(self) -> None:
        # Quotes don't need escaping in Telegram HTML body content.
        assert escape_telegram_html('He said "hi"') == 'He said "hi"'
        assert escape_telegram_html("it's fine") == "it's fine"

    def test_preserves_unicode(self) -> None:
        # Emoji and non-ASCII characters must pass through unchanged.
        assert escape_telegram_html("⚙️ café") == "⚙️ café"

    def test_empty_string(self) -> None:
        assert escape_telegram_html("") == ""

    def test_no_special_chars_is_identity(self) -> None:
        assert escape_telegram_html("plain text 123") == "plain text 123"


class TestEscapeTelegramAttr:
    def test_escapes_quotes_in_addition_to_html(self) -> None:
        # Attribute values must escape "&'< > — all of them.
        assert escape_telegram_attr('he said "hi"') == "he said &quot;hi&quot;"

    def test_escapes_ampersand_in_query_string(self) -> None:
        assert (
            escape_telegram_attr("https://example.com/?a=1&b=2")
            == "https://example.com/?a=1&amp;b=2"
        )

    def test_empty_string(self) -> None:
        assert escape_telegram_attr("") == ""


class TestEscapeSlackText:
    def test_escapes_the_three_slack_specials(self) -> None:
        # Slack documents exactly three characters needing escape.
        assert escape_slack_text("<>&") == "&lt;&gt;&amp;"

    def test_ampersand_first_so_subsequent_escapes_dont_double(self) -> None:
        # If `&` were replaced last, the `&lt;` and `&gt;` would be
        # turned into `&amp;lt;` and `&amp;gt;`. This test pins the
        # implementation order.
        assert escape_slack_text("<a & b>") == "&lt;a &amp; b&gt;"

    def test_leaves_asterisks_and_underscores_alone(self) -> None:
        # Slack markdown uses *bold*, _italic_, ~strike~ — these are
        # syntax, not content-escape targets.
        assert escape_slack_text("*bold*") == "*bold*"
        assert escape_slack_text("_italic_") == "_italic_"

    def test_empty_string(self) -> None:
        assert escape_slack_text("") == ""


class TestEscapeSlackUrl:
    def test_strips_angle_brackets(self) -> None:
        assert escape_slack_url("https://example.com/>") == "https://example.com/"

    def test_strips_pipe(self) -> None:
        # A `|` in the URL would split it from its visible text in
        # Slack's `<url|text>` syntax.
        assert escape_slack_url("https://example.com/?a|b") == "https://example.com/?ab"

    def test_well_formed_url_is_identity(self) -> None:
        assert escape_slack_url("https://example.com/path?a=1") == (
            "https://example.com/path?a=1"
        )

    def test_empty_string(self) -> None:
        assert escape_slack_url("") == ""
