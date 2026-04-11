from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog

from datronis_relay.core.ports import ClaudeClientProtocol
from datronis_relay.domain.attachments import FileAttachment
from datronis_relay.domain.errors import ClaudeApiError
from datronis_relay.domain.messages import ClaudeRequest
from datronis_relay.domain.stream_events import (
    CompletionEvent,
    StreamEvent,
    TextChunk,
    Usage,
)

log = structlog.get_logger(__name__)


class ClaudeAgentClient(ClaudeClientProtocol):
    """Thin wrapper over the official `claude-agent-sdk` Python package.

    This is the ONLY module in the project that imports the SDK. If the SDK
    surface changes between versions, this file — and ideally `_extract_*`
    functions alone — is the only thing that needs updating.
    """

    def __init__(self, model: str, max_turns: int = 10) -> None:
        self._model = model
        self._max_turns = max_turns

    async def stream(self, request: ClaudeRequest) -> AsyncIterator[StreamEvent]:
        try:
            from claude_agent_sdk import ClaudeAgentOptions, query
        except ImportError as exc:  # pragma: no cover
            raise ClaudeApiError(
                "claude-agent-sdk is not installed",
                correlation_id=request.correlation_id,
            ) from exc

        options_kwargs: dict[str, Any] = {
            "model": self._model,
            "max_turns": self._max_turns,
        }
        if request.allowed_tools:
            options_kwargs["allowed_tools"] = list(request.allowed_tools)

        options = ClaudeAgentOptions(**options_kwargs)

        effective_prompt = _build_prompt(request.prompt, request.attachments)

        log.info(
            "claude.stream.start",
            session_id=request.session_id,
            model=self._model,
            allowed_tools=list(request.allowed_tools) or None,
            attachments=len(request.attachments),
        )

        total_in = 0
        total_out = 0

        try:
            async for message in query(prompt=effective_prompt, options=options):
                text = _extract_text(message)
                if text:
                    yield TextChunk(text=text)
                usage_in, usage_out = _extract_usage(message)
                total_in += usage_in
                total_out += usage_out
        except ClaudeApiError:
            raise
        except Exception as exc:  # SDK surface is broad
            log.exception("claude.stream.error", error=str(exc))
            raise ClaudeApiError(
                f"claude agent sdk failed: {exc}",
                correlation_id=request.correlation_id,
            ) from exc
        finally:
            log.info(
                "claude.stream.end",
                session_id=request.session_id,
                tokens_in=total_in,
                tokens_out=total_out,
            )

        yield CompletionEvent(
            usage=Usage(
                tokens_in=total_in,
                tokens_out=total_out,
                cost_usd=0.0,  # CostTracker fills this in when recording
            )
        )

    async def aclose(self) -> None:
        return None


def _extract_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            block_text = getattr(block, "text", None)
            if isinstance(block_text, str):
                parts.append(block_text)
        if parts:
            return "".join(parts)
    return ""


def _build_prompt(text: str, attachments: tuple[FileAttachment, ...]) -> str:
    """Compose a prompt that tells Claude about any attached files.

    We pass the absolute paths and leave the actual reading to Claude's
    Read tool. This keeps the SDK wrapper single-responsibility and works
    for both text files and images (Claude's Read tool is multimodal).
    """
    if not attachments:
        return text
    lines = [text.strip()] if text.strip() else []
    lines.append("")
    lines.append("Attached files (please use the Read tool to inspect them):")
    for att in attachments:
        kind = "image" if att.is_image() else "file"
        lines.append(
            f"- {att.path}  ({att.filename}, {att.mime_type}, {att.size_bytes} bytes, {kind})"
        )
    return "\n".join(lines)


def _extract_usage(message: Any) -> tuple[int, int]:
    """Best-effort usage extraction from a single SDK message.

    Typically only the terminal ResultMessage carries a `usage` object;
    every other message returns (0, 0) and simply doesn't contribute.
    """
    usage = getattr(message, "usage", None)
    if usage is None:
        return (0, 0)
    tin = getattr(usage, "input_tokens", None)
    tout = getattr(usage, "output_tokens", None)
    return (
        int(tin) if isinstance(tin, (int, float)) else 0,
        int(tout) if isinstance(tout, (int, float)) else 0,
    )
