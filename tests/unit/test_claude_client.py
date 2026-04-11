"""Tests for the pure helpers inside `infrastructure/claude_client.py`.

The `ClaudeAgentClient.stream()` method lazy-imports `claude_agent_sdk`
inside the method body so these tests run without the SDK installed.
We exercise the three pure helpers (`_build_prompt`, `_extract_text`,
`_extract_usage`) and the construction/close lifecycle of the client.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from datronis_relay.domain.attachments import FileAttachment
from datronis_relay.infrastructure.claude_client import (
    ClaudeAgentClient,
    _build_prompt,
    _extract_text,
    _extract_usage,
)


def _file_attachment(filename: str = "report.pdf", mime: str = "application/pdf") -> FileAttachment:
    return FileAttachment(
        path=Path(f"/tmp/{filename}"),
        filename=filename,
        mime_type=mime,
        size_bytes=1234,
    )


class TestBuildPrompt:
    def test_no_attachments_returns_text_unchanged(self) -> None:
        assert _build_prompt("hello world", ()) == "hello world"

    def test_empty_text_without_attachments(self) -> None:
        assert _build_prompt("", ()) == ""

    def test_file_attachment_is_listed(self) -> None:
        att = _file_attachment()
        prompt = _build_prompt("summarize this", (att,))
        assert "summarize this" in prompt
        assert "/tmp/report.pdf" in prompt
        assert "report.pdf" in prompt
        assert "application/pdf" in prompt
        assert "file" in prompt  # kind marker

    def test_image_attachment_is_marked_as_image(self) -> None:
        img = _file_attachment(filename="screenshot.png", mime="image/png")
        prompt = _build_prompt("what's in this?", (img,))
        assert "image" in prompt
        assert "screenshot.png" in prompt

    def test_multiple_attachments_all_listed(self) -> None:
        a = _file_attachment(filename="a.pdf", mime="application/pdf")
        b = _file_attachment(filename="b.txt", mime="text/plain")
        prompt = _build_prompt("compare", (a, b))
        assert "a.pdf" in prompt
        assert "b.txt" in prompt

    def test_empty_prompt_with_attachments(self) -> None:
        att = _file_attachment()
        prompt = _build_prompt("", (att,))
        assert "report.pdf" in prompt
        # No prompt line, just the attachments header + entry
        assert "Attached files" in prompt


class TestExtractText:
    def test_string_content(self) -> None:
        message = SimpleNamespace(content="hello")
        assert _extract_text(message) == "hello"

    def test_list_of_text_blocks(self) -> None:
        block1 = SimpleNamespace(text="foo ")
        block2 = SimpleNamespace(text="bar")
        message = SimpleNamespace(content=[block1, block2])
        assert _extract_text(message) == "foo bar"

    def test_list_with_non_text_blocks_skips_them(self) -> None:
        text_block = SimpleNamespace(text="keep")
        image_block = SimpleNamespace(data="binary")  # no .text
        message = SimpleNamespace(content=[text_block, image_block])
        assert _extract_text(message) == "keep"

    def test_empty_list_content_returns_empty(self) -> None:
        message = SimpleNamespace(content=[])
        assert _extract_text(message) == ""

    def test_missing_content_returns_empty(self) -> None:
        message = SimpleNamespace()
        assert _extract_text(message) == ""

    def test_list_with_no_text_blocks_returns_empty(self) -> None:
        block = SimpleNamespace(data="binary")
        message = SimpleNamespace(content=[block])
        assert _extract_text(message) == ""


class TestExtractUsage:
    def test_usage_with_both_token_counts(self) -> None:
        usage = SimpleNamespace(input_tokens=100, output_tokens=200)
        message = SimpleNamespace(usage=usage)
        assert _extract_usage(message) == (100, 200)

    def test_missing_usage_returns_zero_zero(self) -> None:
        message = SimpleNamespace()
        assert _extract_usage(message) == (0, 0)

    def test_usage_with_none_token_counts(self) -> None:
        usage = SimpleNamespace(input_tokens=None, output_tokens=None)
        message = SimpleNamespace(usage=usage)
        assert _extract_usage(message) == (0, 0)

    def test_usage_with_missing_output_tokens(self) -> None:
        usage = SimpleNamespace(input_tokens=50)  # no output_tokens
        message = SimpleNamespace(usage=usage)
        assert _extract_usage(message) == (50, 0)

    def test_usage_with_float_tokens_is_coerced_to_int(self) -> None:
        usage = SimpleNamespace(input_tokens=10.0, output_tokens=20.7)
        message = SimpleNamespace(usage=usage)
        assert _extract_usage(message) == (10, 20)


class TestClaudeAgentClientLifecycle:
    def test_construction_stores_model_and_max_turns(self) -> None:
        client = ClaudeAgentClient(model="claude-sonnet-4-6", max_turns=5)
        assert client._model == "claude-sonnet-4-6"
        assert client._max_turns == 5

    def test_construction_defaults_max_turns_to_ten(self) -> None:
        client = ClaudeAgentClient(model="claude-opus-4-6")
        assert client._max_turns == 10

    async def test_aclose_is_a_noop(self) -> None:
        client = ClaudeAgentClient(model="claude-sonnet-4-6")
        result = await client.aclose()
        assert result is None
