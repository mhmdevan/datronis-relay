"""Unit tests for `PassthroughFormatter`.

The Phase M-0 contract: this formatter must be byte-identical to the
pre-M-0 `_send_chunked` behaviour. These tests pin that contract.
"""

from __future__ import annotations

from datronis_relay.core.chunking import CONTINUATION_MARKER, chunk_message
from datronis_relay.infrastructure.formatting.passthrough import PassthroughFormatter


def test_empty_input_returns_empty_list() -> None:
    assert PassthroughFormatter().format("", max_chars=4000) == []


def test_whitespace_only_input_returns_empty_list() -> None:
    # "(claude returned no content)" is injected higher up in the
    # pipeline — the formatter itself should just say "nothing to send".
    assert PassthroughFormatter().format("   \n\t  ", max_chars=4000) == []


def test_short_input_is_a_single_chunk_unchanged() -> None:
    text = "hello world"
    assert PassthroughFormatter().format(text, max_chars=4000) == [text]


def test_input_over_limit_splits_and_adds_continuation_marker() -> None:
    text = "line one\nline two\nline three\nline four\nline five"
    chunks = PassthroughFormatter().format(text, max_chars=25)
    assert len(chunks) >= 2
    # Every non-final chunk carries the continuation marker.
    for chunk in chunks[:-1]:
        assert chunk.endswith(CONTINUATION_MARKER)
    # Every chunk respects the limit.
    for chunk in chunks:
        assert len(chunk) <= 25


def test_preserves_raw_markdown_literally() -> None:
    # M-0 does NO markdown transformation — the ## must come out as ##.
    text = "## heading\n\n**bold** and *italic*"
    assert PassthroughFormatter().format(text, max_chars=4000) == [text]


def test_preserves_unicode() -> None:
    text = "⚙️ CPU: Intel Xeon — 5 vCores 日本語"
    assert PassthroughFormatter().format(text, max_chars=4000) == [text]


def test_format_is_stateless_across_calls() -> None:
    # The same instance must give the same answer no matter how it's used.
    formatter = PassthroughFormatter()
    a = formatter.format("first", max_chars=100)
    b = formatter.format("second", max_chars=100)
    c = formatter.format("first", max_chars=100)
    assert a == c
    assert a != b


def test_matches_legacy_behaviour_for_the_size_the_pipeline_used_before() -> None:
    # Before M-0, `_send_chunked` called `chunk_message(text, limit=channel.max_message_length)`.
    # The passthrough formatter must produce the same output for that path.
    text = "a" * 4050  # just over the 4000-char Telegram limit
    legacy = chunk_message(text, limit=4000)
    new = PassthroughFormatter().format(text, max_chars=4000)
    assert legacy == new
