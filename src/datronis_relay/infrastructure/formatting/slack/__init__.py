"""Slack-specific formatter.

Phase M-2 delivery:

  * `SlackMrkdwnFormatter` — implements `MessageFormatter`. Parses
    markdown, renders to Slack's mrkdwn dialect, chunks at `max_chars`.
  * `render_slack_mrkdwn` — pure AST → list[RenderedBlock] converter.
"""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.slack.formatter import (
    SlackMrkdwnFormatter,
)
from datronis_relay.infrastructure.formatting.slack.renderer import (
    render_slack_mrkdwn,
)

__all__ = ["SlackMrkdwnFormatter", "render_slack_mrkdwn"]
