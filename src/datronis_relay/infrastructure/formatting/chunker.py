"""Pure block-level chunker used by every platform formatter.

The Phase M-1/M-2 renderers produce a *sequence of rendered blocks* —
paragraphs, lists, code blocks, tables — each knowing how long it is
and whether it can be split internally. This module greedy-packs those
blocks into chunks of ≤ `max_chars` codepoints at safe boundaries.

Invariants (enforced by `tests/unit/test_formatting_chunker.py`):

  1. `len(chunk) <= max_chars` for every chunk.
  2. No chunk is empty.
  3. Blocks appear in the output in input order.
  4. An empty input or an iterable of only empty blocks yields `[]`.
  5. A single block whose text is ≤ max_chars always fits in exactly one chunk.
  6. Blocks marked `splittable=False` are never split mid-content
     unless they individually exceed max_chars *and* the caller gave
     no alternative — in that last-resort case the chunker hard-wraps
     at the character limit (documented, verified by test).

Roadmap reference: `datronis-relay-message-formatting-roadmap.md` §7.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

BLOCK_SEPARATOR = "\n\n"


@dataclass(frozen=True, slots=True)
class RenderedBlock:
    """One unit of platform-native rendered output.

    Attributes:
        text: the rendered content as a single string. May contain
            internal newlines (e.g. a multi-line code block).
        splittable: if True, and this block alone exceeds `max_chars`,
            the chunker is allowed to split it on newline boundaries.
            Code blocks and tables set this to False because splitting
            would produce invalid markup (orphaned ```-fences, missing
            table headers).
    """

    text: str
    splittable: bool = True


def chunk_blocks(blocks: Iterable[RenderedBlock], max_chars: int) -> list[str]:
    """Greedy-pack `blocks` into chunks of ≤ `max_chars` codepoints.

    Within a chunk, consecutive blocks are joined with a blank line
    (``\\n\\n``). A block whose text is longer than `max_chars` is
    normalized to multiple sub-pieces before packing:

      - `splittable=True` → split on the last newline before the limit.
      - `splittable=False` → hard-wrap at `max_chars` (last resort).
    """
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")

    pieces: list[str] = []
    for block in blocks:
        if not block.text:
            continue
        if len(block.text) <= max_chars:
            pieces.append(block.text)
        elif block.splittable:
            pieces.extend(_split_on_newlines(block.text, max_chars))
        else:
            pieces.extend(_hard_wrap(block.text, max_chars))

    return _greedy_pack(pieces, max_chars)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _split_on_newlines(text: str, max_chars: int) -> list[str]:
    """Break `text` into pieces ≤ max_chars, preferring newline boundaries."""
    pieces: list[str] = []
    remaining = text
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at <= 0:
            # No newline within the window — fall through to hard-wrap.
            split_at = max_chars
        head = remaining[:split_at].rstrip()
        if head:
            pieces.append(head)
        remaining = remaining[split_at:].lstrip("\n")
    if remaining:
        pieces.append(remaining)
    return pieces


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    """Last-resort fixed-width splitter. Splits on exact codepoint boundaries."""
    return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]


def _greedy_pack(pieces: list[str], max_chars: int) -> list[str]:
    """Combine adjacent pieces into chunks of ≤ max_chars, joined by a blank line."""
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
            continue
        candidate = current + BLOCK_SEPARATOR + piece
        if len(candidate) <= max_chars:
            current = candidate
        else:
            chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    return chunks
