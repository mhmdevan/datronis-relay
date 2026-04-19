"""Unit tests for the block-level chunker.

These enforce the invariants documented in the roadmap §7. Every future
formatter relies on this chunker; a regression here breaks every adapter.
"""

from __future__ import annotations

import pytest

from datronis_relay.infrastructure.formatting.chunker import (
    BLOCK_SEPARATOR,
    RenderedBlock,
    chunk_blocks,
)

# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_empty_input_returns_empty_list(self) -> None:
        assert chunk_blocks([], max_chars=100) == []

    def test_blocks_with_empty_text_are_filtered(self) -> None:
        blocks = [RenderedBlock(""), RenderedBlock("hello"), RenderedBlock("")]
        assert chunk_blocks(blocks, max_chars=100) == ["hello"]

    def test_single_small_block(self) -> None:
        assert chunk_blocks([RenderedBlock("hello")], max_chars=100) == ["hello"]

    def test_multiple_small_blocks_pack_into_one_chunk(self) -> None:
        blocks = [RenderedBlock("a"), RenderedBlock("b"), RenderedBlock("c")]
        assert chunk_blocks(blocks, max_chars=100) == ["a\n\nb\n\nc"]

    def test_blocks_are_joined_with_blank_line(self) -> None:
        blocks = [RenderedBlock("first"), RenderedBlock("second")]
        chunks = chunk_blocks(blocks, max_chars=100)
        assert chunks == ["first" + BLOCK_SEPARATOR + "second"]


# ---------------------------------------------------------------------------
# Packing across chunks
# ---------------------------------------------------------------------------


class TestPacking:
    def test_packs_until_next_block_would_overflow(self) -> None:
        # 3 x 5-char blocks. With separator "\n\n" (2 chars):
        #   "aaaaa\n\nbbbbb" = 12 chars
        #   "aaaaa\n\nbbbbb\n\nccccc" = 19 chars
        # With max_chars=15, only the first two fit in one chunk.
        blocks = [RenderedBlock("aaaaa"), RenderedBlock("bbbbb"), RenderedBlock("ccccc")]
        chunks = chunk_blocks(blocks, max_chars=15)
        assert chunks == ["aaaaa\n\nbbbbb", "ccccc"]

    def test_each_chunk_respects_max_chars(self) -> None:
        blocks = [RenderedBlock("x" * 40) for _ in range(5)]
        chunks = chunk_blocks(blocks, max_chars=50)
        for chunk in chunks:
            assert len(chunk) <= 50

    def test_block_order_is_preserved(self) -> None:
        blocks = [RenderedBlock(s) for s in ["one", "two", "three", "four"]]
        chunks = chunk_blocks(blocks, max_chars=10)
        joined = "|".join(chunks)
        assert joined.index("one") < joined.index("two") < joined.index("three") < joined.index("four")


# ---------------------------------------------------------------------------
# Oversized blocks
# ---------------------------------------------------------------------------


class TestOversizedBlocks:
    def test_splittable_oversized_block_splits_on_newline(self) -> None:
        text = "line one\nline two\nline three"
        chunks = chunk_blocks([RenderedBlock(text, splittable=True)], max_chars=15)
        # Each chunk ≤ 15 chars; newline-split preferred.
        for chunk in chunks:
            assert len(chunk) <= 15
        # All original content is present.
        assert "line one" in "".join(chunks)
        assert "line three" in "".join(chunks)

    def test_non_splittable_oversized_block_hard_wraps(self) -> None:
        # A block 25 chars long, max 10 — we expect hard-wrap at exactly 10.
        text = "a" * 25
        chunks = chunk_blocks([RenderedBlock(text, splittable=False)], max_chars=10)
        for chunk in chunks:
            assert len(chunk) <= 10
        # Full text reconstructable by concatenation (no content loss).
        assert "".join(chunks).replace(BLOCK_SEPARATOR, "") == text

    def test_splittable_single_giant_word_hard_wraps(self) -> None:
        # No newline to split on — the chunker must still respect the bound.
        text = "x" * 100
        chunks = chunk_blocks([RenderedBlock(text, splittable=True)], max_chars=20)
        for chunk in chunks:
            assert len(chunk) <= 20


# ---------------------------------------------------------------------------
# Invariants (the most important checks)
# ---------------------------------------------------------------------------


class TestInvariants:
    """The invariants listed at the top of chunker.py."""

    def test_no_chunk_is_empty(self) -> None:
        blocks = [RenderedBlock("a"), RenderedBlock(""), RenderedBlock("b")]
        for chunk in chunk_blocks(blocks, max_chars=100):
            assert chunk != ""

    def test_no_chunk_exceeds_max_chars(self) -> None:
        # Property-ish check with a mixed input.
        blocks = [
            RenderedBlock("short"),
            RenderedBlock("x" * 50, splittable=True),
            RenderedBlock("y" * 200, splittable=False),
            RenderedBlock("z" * 30),
        ]
        for chunk in chunk_blocks(blocks, max_chars=40):
            assert len(chunk) <= 40

    def test_single_block_leq_max_chars_fits_in_one_chunk(self) -> None:
        for n in (1, 50, 99, 100):
            text = "a" * n
            chunks = chunk_blocks([RenderedBlock(text)], max_chars=100)
            assert chunks == [text]


# ---------------------------------------------------------------------------
# Boundary / error cases
# ---------------------------------------------------------------------------


class TestBoundaries:
    def test_max_chars_zero_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_blocks([RenderedBlock("hello")], max_chars=0)

    def test_max_chars_negative_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_blocks([RenderedBlock("hello")], max_chars=-10)

    def test_block_exactly_matches_max_chars(self) -> None:
        text = "x" * 10
        chunks = chunk_blocks([RenderedBlock(text)], max_chars=10)
        assert chunks == [text]

    def test_two_blocks_whose_combined_length_just_fits(self) -> None:
        # "a\n\nb" = 4 chars exactly.
        chunks = chunk_blocks([RenderedBlock("a"), RenderedBlock("b")], max_chars=4)
        assert chunks == ["a\n\nb"]

    def test_two_blocks_whose_combined_length_just_exceeds(self) -> None:
        # "a\n\nb" = 4 chars — does not fit in 3.
        chunks = chunk_blocks([RenderedBlock("a"), RenderedBlock("b")], max_chars=3)
        assert chunks == ["a", "b"]
