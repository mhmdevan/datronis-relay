from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from datronis_relay.domain.attachments import FileAttachment
from datronis_relay.domain.ids import CorrelationId, SessionId, UserId


class Platform(StrEnum):
    TELEGRAM = "telegram"
    SLACK = "slack"
    DISCORD = "discord"


class MessageKind(StrEnum):
    TEXT = "text"
    VOICE = "voice"  # reserved for Phase 2.5


@dataclass(frozen=True, slots=True)
class PlatformMessage:
    """Immutable inbound message crossing the adapter → core boundary.

    Phase 4 added two fields:
      - `attachments`: any files the user uploaded with this message.
        Temp files are cleaned up by the pipeline's finally block.
      - `channel_ref`: platform-specific identifier the scheduler uses
        to reconstruct a reply channel for a scheduled task. Empty for
        messages that don't need to be repliable out-of-band.
    """

    correlation_id: CorrelationId
    platform: Platform
    user_id: UserId
    text: str
    kind: MessageKind = MessageKind.TEXT
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    attachments: tuple[FileAttachment, ...] = ()
    channel_ref: str = ""


@dataclass(frozen=True, slots=True)
class ClaudeRequest:
    """What the core asks the Claude client to do.

    `allowed_tools` is the per-user tool allowlist: an empty tuple means
    "no restriction" (let the SDK default apply); any non-empty tuple is
    forwarded to `ClaudeAgentOptions.allowed_tools` verbatim.

    `attachments` is the set of files Claude should be able to read via
    its Read tool. The wrapper in `claude_client.py` adds a line to the
    prompt for each attachment.
    """

    correlation_id: CorrelationId
    session_id: SessionId
    user_id: UserId
    prompt: str
    allowed_tools: tuple[str, ...] = ()
    attachments: tuple[FileAttachment, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaudeResponse:
    """A finalized Claude reply with usage metadata."""

    correlation_id: CorrelationId
    session_id: SessionId
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
