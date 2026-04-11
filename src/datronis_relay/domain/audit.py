from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from datronis_relay.domain.ids import CorrelationId, UserId


class AuditEventType(StrEnum):
    MESSAGE_IN = "msg_in"
    MESSAGE_OUT = "msg_out"
    AUTH_FAIL = "auth_fail"
    RATE_LIMIT = "rate_limit"
    CLAUDE_OK = "claude_ok"
    CLAUDE_ERROR = "claude_error"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Immutable audit log record.

    Every inbound message + every Claude call becomes one of these. The
    `audit_log` table is append-only; there is no update path.
    """

    ts: datetime
    correlation_id: CorrelationId
    user_id: UserId
    event_type: AuditEventType
    tool: str | None = None
    command: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    error_category: str | None = None
