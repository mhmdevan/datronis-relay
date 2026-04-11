from __future__ import annotations

import pytest

from datronis_relay.core.chunking import (
    CONTINUATION_MARKER,
    DEFAULT_LIMIT,
    chunk_message,
)


class TestChunkMessage:
    def test_empty_message_is_returned_unchanged(self) -> None:
        assert chunk_message("") == [""]

    def test_short_message_fits_in_one_chunk(self) -> None:
        assert chunk_message("hello world") == ["hello world"]

    def test_exact_limit_fits_in_one_chunk(self) -> None:
        text = "a" * DEFAULT_LIMIT
        chunks = chunk_message(text)
        assert chunks == [text]
        assert not chunks[0].endswith(CONTINUATION_MARKER)

    def test_over_limit_produces_multiple_chunks(self) -> None:
        text = "a" * (DEFAULT_LIMIT + 500)
        chunks = chunk_message(text)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert len(chunk) <= DEFAULT_LIMIT

    def test_splits_on_newline_boundary_when_possible(self) -> None:
        part_a = "a" * 3500
        part_b = "b" * 2000
        text = f"{part_a}\n{part_b}"
        chunks = chunk_message(text)
        assert len(chunks) == 2
        assert chunks[0].startswith("a")
        assert chunks[1].startswith("b")

    def test_continuation_marker_on_every_chunk_except_last(self) -> None:
        text = "x" * 10_000
        chunks = chunk_message(text)
        assert len(chunks) >= 3
        for chunk in chunks[:-1]:
            assert chunk.endswith(CONTINUATION_MARKER)
        assert not chunks[-1].endswith(CONTINUATION_MARKER)

    def test_hard_split_when_no_newlines_available(self) -> None:
        text = "x" * (DEFAULT_LIMIT * 2 + 10)
        chunks = chunk_message(text)
        assert len(chunks) == 3
        for chunk in chunks:
            assert len(chunk) <= DEFAULT_LIMIT

    def test_reassembling_chunks_yields_the_original_payload(self) -> None:
        text = "\n".join(f"line {i}: " + "z" * 100 for i in range(200))
        chunks = chunk_message(text)
        stripped = [c.removesuffix(CONTINUATION_MARKER).rstrip() for c in chunks]
        joined_tokens = " ".join(" ".join(s.split()) for s in stripped)
        assert "line 0:" in joined_tokens
        assert "line 199:" in joined_tokens

    def test_invalid_limit_raises(self) -> None:
        with pytest.raises(ValueError):
            chunk_message("hello", limit=5)

    def test_custom_larger_limit_slack_sized(self) -> None:
        """Slack allows ~38k chars per message — chunking should honor any
        explicit limit, not silently clamp to the Telegram default."""
        text = "s" * 50_000
        chunks = chunk_message(text, limit=38_000)
        assert len(chunks) == 2
        for chunk in chunks:
            assert len(chunk) <= 38_000

    def test_custom_smaller_limit_triggers_more_chunks(self) -> None:
        text = "a" * 1000
        chunks = chunk_message(text, limit=200)
        assert len(chunks) >= 5
        for chunk in chunks:
            assert len(chunk) <= 200
