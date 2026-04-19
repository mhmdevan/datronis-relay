"""Unit tests for the markdown-stripping fallback helper."""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.strip_markdown import strip_markdown


class TestEmpty:
    def test_empty_string(self) -> None:
        assert strip_markdown("") == ""

    def test_whitespace_only(self) -> None:
        assert strip_markdown("   \n\t  ") == ""

    def test_plain_text_unchanged(self) -> None:
        assert strip_markdown("hello world") == "hello world"


class TestHeadings:
    def test_h1(self) -> None:
        assert strip_markdown("# Title") == "Title"

    def test_h3(self) -> None:
        assert strip_markdown("### Sub") == "Sub"

    def test_h6(self) -> None:
        assert strip_markdown("###### Deep") == "Deep"

    def test_heading_in_context(self) -> None:
        assert strip_markdown("# Title\n\nBody text") == "Title\n\nBody text"


class TestBoldItalic:
    def test_double_asterisk_bold(self) -> None:
        assert strip_markdown("**bold**") == "bold"

    def test_single_asterisk_italic(self) -> None:
        assert strip_markdown("*italic*") == "italic"

    def test_triple_asterisk_bold_italic(self) -> None:
        assert strip_markdown("***both***") == "both"

    def test_underscore_bold(self) -> None:
        assert strip_markdown("__bold__") == "bold"

    def test_underscore_italic(self) -> None:
        assert strip_markdown("_italic_") == "italic"

    def test_strikethrough(self) -> None:
        assert strip_markdown("~~struck~~") == "struck"

    def test_mixed_inline(self) -> None:
        result = strip_markdown("**bold** and *italic* and ~~strike~~")
        assert result == "bold and italic and strike"


class TestCode:
    def test_inline_backtick(self) -> None:
        assert strip_markdown("run `ls` now") == "run ls now"

    def test_double_backtick(self) -> None:
        assert strip_markdown("use ``code`` here") == "use code here"

    def test_fenced_code_block(self) -> None:
        md = "```python\nprint('hi')\n```"
        assert strip_markdown(md) == "print('hi')"

    def test_fenced_code_no_language(self) -> None:
        md = "```\nplain code\n```"
        assert strip_markdown(md) == "plain code"

    def test_tilde_fenced_code(self) -> None:
        md = "~~~\nfenced\n~~~"
        assert strip_markdown(md) == "fenced"


class TestLinks:
    def test_link_keeps_label(self) -> None:
        assert strip_markdown("[click](https://example.com)") == "click"

    def test_image_keeps_alt(self) -> None:
        assert strip_markdown("![logo](https://example.com/img.png)") == "logo"

    def test_link_in_context(self) -> None:
        result = strip_markdown("See [docs](https://x.com) for more.")
        assert result == "See docs for more."


class TestTables:
    def test_separator_row_removed(self) -> None:
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        result = strip_markdown(md)
        assert "|---|" not in result
        assert "a" in result
        assert "1" in result

    def test_leading_trailing_pipes_removed(self) -> None:
        md = "| cell1 | cell2 |"
        result = strip_markdown(md)
        assert not result.startswith("|")
        assert not result.endswith("|")


class TestBlockquotes:
    def test_blockquote_marker_removed(self) -> None:
        assert strip_markdown("> quoted line") == "quoted line"

    def test_multiline_blockquote(self) -> None:
        md = "> line one\n> line two"
        result = strip_markdown(md)
        assert result == "line one\nline two"


class TestHorizontalRule:
    def test_triple_dash_removed(self) -> None:
        result = strip_markdown("above\n\n---\n\nbelow")
        assert "---" not in result
        assert "above" in result
        assert "below" in result


class TestBlankLineCollapsing:
    def test_multiple_blank_lines_collapsed(self) -> None:
        md = "a\n\n\n\n\nb"
        result = strip_markdown(md)
        assert result == "a\n\nb"


class TestRealWorldInput:
    def test_server_config_example(self) -> None:
        """The raw markdown that triggered the whole roadmap."""
        md = (
            "## Full Server Configuration\n\n"
            "### CPU\n"
            "| Property | Value |\n"
            "|---|---|\n"
            "| **Model** | Intel Xeon E5-2697A v4 |\n"
            "| **Cores** | 5 |\n"
        )
        result = strip_markdown(md)
        # No markdown syntax should remain.
        assert "##" not in result
        assert "**" not in result
        assert "|---|" not in result
        # But the content should survive.
        assert "Full Server Configuration" in result
        assert "CPU" in result
        assert "Intel Xeon" in result
        assert "5" in result
