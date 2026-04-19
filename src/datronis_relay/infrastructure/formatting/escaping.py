"""Platform-specific escape helpers.

Every text node that a future renderer emits must pass through one of
these. Leaving a `<` or `&` unescaped in Telegram HTML is a parse error
(the whole message fails). Leaving a `<` in Slack mrkdwn turns the rest
of the line into a broken `<...>` tag.

All functions are pure — zero state, zero side effects, trivially
testable. No function mutates its input or calls out to I/O.

Reference:
  - Telegram Bot API, `parse_mode=HTML`:
    https://core.telegram.org/bots/api#html-style
  - Slack mrkdwn escaping:
    https://api.slack.com/reference/surfaces/formatting#escaping
"""

from __future__ import annotations

import html


def escape_telegram_html(text: str) -> str:
    """Escape text for Telegram's `parse_mode=HTML` rendering.

    Converts `<`, `>`, and `&` to their named entities. Other characters
    (including `'` and `"`) are left as-is — Telegram's HTML parser
    accepts them in text content. For attribute values (e.g. `href`),
    use `escape_telegram_attr()` instead.
    """
    return html.escape(text, quote=False)


def escape_telegram_attr(text: str) -> str:
    """Escape text for use inside an HTML attribute value.

    Additionally escapes `"` and `'` so the attribute quoting stays
    intact. Use this for `<a href="...">` URLs and any other attribute
    values (currently only `href` is used in the Telegram renderer).
    """
    return html.escape(text, quote=True)


def escape_slack_text(text: str) -> str:
    """Escape text for Slack mrkdwn body content.

    Slack only requires `<`, `>`, `&` to be escaped. Unlike Telegram,
    Slack uses `&lt;` / `&gt;` / `&amp;` named entities directly — the
    escape is simpler than HTML's full entity set.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def escape_slack_url(url: str) -> str:
    """Sanitize a URL for inclusion in Slack's `<url|text>` link syntax.

    The URL portion of Slack's link syntax must not contain `>` (which
    would close the link prematurely) or `|` (which would split the URL
    from its visible text). Both are stripped defensively — a
    well-formed URI should not contain them, but user-supplied URLs
    sometimes do.
    """
    return url.replace(">", "").replace("|", "")
