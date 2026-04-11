from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Usage:
    """Token + cost accounting for a single Claude response."""

    tokens_in: int
    tokens_out: int
    cost_usd: float


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A streamed text fragment from Claude."""

    text: str


@dataclass(frozen=True, slots=True)
class CompletionEvent:
    """Emitted once, as the final event, with the accumulated usage."""

    usage: Usage


StreamEvent = TextChunk | CompletionEvent
