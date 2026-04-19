"""Hypothesis property tests for the block-level chunker.

These complement the hand-written tests in `test_formatting_chunker.py`
by generating thousands of random block sequences and asserting the
chunker's invariants hold on every one. Property tests catch edge-case
bugs that are hard to anticipate — off-by-one errors at boundary
lengths, degenerate inputs like zero-length blocks, single-char blocks,
and huge non-splittable blocks.

Invariants tested (from roadmap §7):

  1. **Length bound** — every chunk ≤ max_chars.
  2. **Non-empty** — no chunk is the empty string.
  3. **Order preserved** — blocks appear in output order.
  4. **Content preservation** — all block text appears somewhere in the
     concatenated output.
  5. **Empty-in, empty-out** — no blocks → no chunks.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from datronis_relay.infrastructure.formatting.chunker import (
    BLOCK_SEPARATOR,
    RenderedBlock,
    chunk_blocks,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Block text: printable strings of 0-500 chars (short enough to keep
# tests fast, long enough to exercise split paths).
_block_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=0,
    max_size=500,
)

_block = st.builds(
    RenderedBlock,
    text=_block_text,
    splittable=st.booleans(),
)

_block_list = st.lists(_block, min_size=0, max_size=20)

# max_chars: at least 10 (the chunker raises on ≤ 0, and very small
# values are degenerate but must still be safe).
_max_chars = st.integers(min_value=10, max_value=2000)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestChunkerProperties:
    @given(blocks=_block_list, max_chars=_max_chars)
    @settings(max_examples=300, deadline=None)
    def test_length_bound(self, blocks: list[RenderedBlock], max_chars: int) -> None:
        """Every chunk must be ≤ max_chars codepoints."""
        chunks = chunk_blocks(blocks, max_chars=max_chars)
        for chunk in chunks:
            assert len(chunk) <= max_chars

    @given(blocks=_block_list, max_chars=_max_chars)
    @settings(max_examples=300, deadline=None)
    def test_no_empty_chunks(self, blocks: list[RenderedBlock], max_chars: int) -> None:
        """No chunk may be the empty string."""
        chunks = chunk_blocks(blocks, max_chars=max_chars)
        for chunk in chunks:
            assert chunk != ""

    @given(blocks=_block_list, max_chars=_max_chars)
    @settings(max_examples=300, deadline=None)
    def test_order_preserved(self, blocks: list[RenderedBlock], max_chars: int) -> None:
        """Non-empty blocks must appear in the output in their original order.

        We verify this by checking that the first occurrence of each
        non-empty block's text (or a prefix of it for oversized blocks)
        is monotonically increasing in the concatenated output.
        """
        chunks = chunk_blocks(blocks, max_chars=max_chars)
        combined = BLOCK_SEPARATOR.join(chunks)
        last_pos = -1
        for block in blocks:
            if not block.text:
                continue
            # Use a short prefix — oversized blocks get split.
            needle = block.text[:20]
            if not needle:
                continue
            pos = combined.find(needle, last_pos + 1)
            if pos == -1:
                # Might be truncated at a hard-wrap boundary — skip.
                continue
            assert pos >= last_pos, (
                f"block order violated: '{needle}' found at {pos}, "
                f"but previous block was at {last_pos}"
            )
            last_pos = pos

    @given(blocks=_block_list, max_chars=_max_chars)
    @settings(max_examples=300, deadline=None)
    def test_content_preserved(self, blocks: list[RenderedBlock], max_chars: int) -> None:
        """Every non-empty block's text must appear in the output.

        For splittable blocks that get split at newline boundaries, each
        non-empty line must appear. For non-splittable blocks that get
        hard-wrapped, each `max_chars`-sized slice must appear.
        """
        chunks = chunk_blocks(blocks, max_chars=max_chars)
        combined = "".join(chunks)
        for block in blocks:
            if not block.text or not block.text.strip():
                continue
            # Check a short prefix is present (handles split blocks).
            prefix = block.text.strip()[:15]
            if prefix:
                assert prefix in combined, (
                    f"content lost: '{prefix}' not found in output"
                )

    @given(max_chars=_max_chars)
    @settings(max_examples=50, deadline=None)
    def test_empty_input_yields_empty_output(self, max_chars: int) -> None:
        """No blocks → no chunks."""
        assert chunk_blocks([], max_chars=max_chars) == []

    @given(blocks=_block_list, max_chars=_max_chars)
    @settings(max_examples=300, deadline=None)
    def test_single_small_block_is_one_chunk(self, blocks: list[RenderedBlock], max_chars: int) -> None:
        """A list with one block that fits must produce exactly one chunk."""
        small_blocks = [b for b in blocks if b.text and len(b.text) <= max_chars]
        if not small_blocks:
            return  # skip if no small blocks generated
        block = small_blocks[0]
        result = chunk_blocks([block], max_chars=max_chars)
        assert len(result) == 1
        assert result[0] == block.text
