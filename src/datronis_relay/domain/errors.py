from __future__ import annotations

from enum import StrEnum

from datronis_relay.domain.ids import CorrelationId


class ErrorCategory(StrEnum):
    AUTH = "AUTH"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    CLAUDE_API = "CLAUDE_API"
    INTERNAL = "INTERNAL"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class RelayError(Exception):
    """Base for all user-facing errors.

    `user_message()` is the string we're comfortable sending back to a chat
    client. It never contains stack traces, secrets, or platform internals.
    """

    category: ErrorCategory = ErrorCategory.INTERNAL

    def __init__(
        self,
        message: str,
        *,
        correlation_id: CorrelationId | None = None,
    ) -> None:
        super().__init__(message)
        self.correlation_id = correlation_id

    def user_message(self) -> str:
        base = f"[{self.category.value}] {self.args[0]}"
        if self.correlation_id:
            base = f"{base} (ref: {self.correlation_id})"
        return base


class AuthError(RelayError):
    category = ErrorCategory.AUTH


class RateLimitError(RelayError):
    category = ErrorCategory.RATE_LIMIT


class RelayTimeoutError(RelayError):
    category = ErrorCategory.TIMEOUT


class ClaudeApiError(RelayError):
    category = ErrorCategory.CLAUDE_API


class InternalError(RelayError):
    category = ErrorCategory.INTERNAL


class NotImplementedCommandError(RelayError):
    category = ErrorCategory.NOT_IMPLEMENTED
