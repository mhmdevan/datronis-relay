"""Unit tests for the long code-block splitter."""

from __future__ import annotations

from datronis_relay.infrastructure.formatting import (
    SlackMrkdwnFormatter,
    TelegramHtmlFormatter,
)
from datronis_relay.infrastructure.formatting.code_split import split_code_block


def _simple_wrap(code: str, label: str) -> str:
    """Test wrapper mimicking Telegram <pre>."""
    lbl = f" {label}" if label else ""
    return f"<pre>{code}{lbl}</pre>"


def _fence_wrap(code: str, label: str) -> str:
    """Test wrapper mimicking Slack ```."""
    lbl = f" {label}" if label else ""
    return f"```\n{code}{lbl}\n```"


class TestFitsInOneBlock:
    def test_short_code_returns_one_block_no_label(self) -> None:
        blocks = split_code_block("print('hi')", max_chars=200, wrap_fn=_simple_wrap)
        assert len(blocks) == 1
        assert "(part" not in blocks[0].text
        assert blocks[0].text == "<pre>print('hi')</pre>"

    def test_exactly_at_limit_returns_one_block(self) -> None:
        code = "x" * 50
        wrapped = _simple_wrap(code, "")
        blocks = split_code_block(code, max_chars=len(wrapped), wrap_fn=_simple_wrap)
        assert len(blocks) == 1


class TestSplitsCorrectly:
    def test_splits_long_code_into_multiple_parts(self) -> None:
        lines = [f"line {i}" for i in range(100)]
        code = "\n".join(lines)
        blocks = split_code_block(code, max_chars=200, wrap_fn=_simple_wrap)
        assert len(blocks) > 1
        for block in blocks:
            assert block.splittable is False

    def test_each_part_has_label(self) -> None:
        code = "\n".join(f"line {i}" for i in range(50))
        blocks = split_code_block(code, max_chars=150, wrap_fn=_simple_wrap)
        n = len(blocks)
        assert n >= 2
        for i, block in enumerate(blocks, start=1):
            assert f"(part {i}/{n})" in block.text

    def test_every_part_respects_max_chars(self) -> None:
        code = "\n".join(f"# line {i}: some content here" for i in range(200))
        for max_chars in (200, 500, 1000):
            blocks = split_code_block(code, max_chars=max_chars, wrap_fn=_simple_wrap)
            for block in blocks:
                assert len(block.text) <= max_chars, (
                    f"block exceeds {max_chars}: {len(block.text)} chars"
                )

    def test_all_code_content_preserved(self) -> None:
        lines = [f"line_{i}" for i in range(30)]
        code = "\n".join(lines)
        blocks = split_code_block(code, max_chars=150, wrap_fn=_simple_wrap)
        combined = " ".join(b.text for b in blocks)
        for line in lines:
            assert line in combined, f"missing: {line}"


class TestSlackFence:
    def test_slack_style_wrapping(self) -> None:
        code = "\n".join(f"echo {i}" for i in range(50))
        blocks = split_code_block(code, max_chars=200, wrap_fn=_fence_wrap)
        for block in blocks:
            assert block.text.startswith("```\n")
            assert block.text.endswith("\n```")

    def test_fence_balance_in_every_part(self) -> None:
        code = "\n".join(f"echo {i}" for i in range(50))
        blocks = split_code_block(code, max_chars=200, wrap_fn=_fence_wrap)
        for block in blocks:
            assert block.text.count("```") == 2


class TestTelegramIntegration:
    def test_telegram_formatter_splits_huge_code_block(self) -> None:
        """The Phase M-1 known limitation is now fixed."""
        big_code = "```python\n" + "\n".join(
            f"print('line {i}')" for i in range(200)
        ) + "\n```"
        md = f"# Title\n\n{big_code}\n\nDone."
        chunks = TelegramHtmlFormatter().format(md, max_chars=1000)
        for chunk in chunks:
            assert len(chunk) <= 1000
            assert chunk.count("<pre>") == chunk.count("</pre>"), (
                "unbalanced <pre> in chunk"
            )

    def test_slack_formatter_splits_huge_code_block(self) -> None:
        big_code = "```bash\n" + "\n".join(
            f"echo 'line {i}'" for i in range(200)
        ) + "\n```"
        md = f"# Title\n\n{big_code}\n\nDone."
        chunks = SlackMrkdwnFormatter().format(md, max_chars=1000)
        for chunk in chunks:
            assert len(chunk) <= 1000
            assert chunk.count("```") % 2 == 0, "unbalanced ``` in chunk"
