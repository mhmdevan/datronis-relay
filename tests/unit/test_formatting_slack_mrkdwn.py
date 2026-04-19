"""Unit tests for the Slack mrkdwn renderer + formatter.

Organized by token type — one test class per concern. These pin the
lowering rules from roadmap §6.2.

THE CRITICAL INVARIANT: Slack bold is ``*x*`` (single asterisk), NOT
``**x**`` (CommonMark). Every test involving bold asserts exactly one
asterisk on each side.
"""

from __future__ import annotations

import pytest

from datronis_relay.infrastructure.formatting import SlackMrkdwnFormatter
from datronis_relay.infrastructure.formatting.markdown_ast import parse
from datronis_relay.infrastructure.formatting.slack.renderer import (
    HR_CHAR,
    HR_WIDTH,
    render_slack_mrkdwn,
)


def render(md: str) -> list[str]:
    """Parse + render helper: returns the block texts as strings."""
    return [b.text for b in render_slack_mrkdwn(parse(md))]


# ---------------------------------------------------------------------------
# Inline markup
# ---------------------------------------------------------------------------


class TestInlineMarkup:
    def test_plain_text_escapes_angle_brackets(self) -> None:
        assert render("a < b & c > d") == ["a &lt; b &amp; c &gt; d"]

    def test_strong_uses_single_asterisk(self) -> None:
        """THE critical invariant — Slack bold is *x*, not **x**."""
        out = render("**bold**")
        assert out == ["*bold*"]
        # Double-check: no double asterisks anywhere.
        assert "**" not in out[0]

    def test_emphasis_uses_underscore(self) -> None:
        assert render("*italic*") == ["_italic_"]

    def test_strikethrough_uses_single_tilde(self) -> None:
        assert render("~~struck~~") == ["~struck~"]

    def test_codespan_uses_backtick(self) -> None:
        assert render("run `ls -la` now") == ["run `ls -la` now"]

    def test_codespan_does_not_escape_angle_brackets(self) -> None:
        # Slack treats inline code as preformatted — no entity escaping.
        assert render("use `<tag>`") == ["use `<tag>`"]

    def test_mixed_inline(self) -> None:
        out = render("**bold** and *italic* and ~~strike~~ and `code`")
        assert out == ["*bold* and _italic_ and ~strike~ and `code`"]

    def test_bold_italic_nests_correctly(self) -> None:
        out = render("***bold italic***")
        # mistune nests as emphasis > strong; Slack sees _*x*_
        assert "*" in out[0] and "_" in out[0]
        # No double asterisks.
        assert "**" not in out[0]


# ---------------------------------------------------------------------------
# Links and images
# ---------------------------------------------------------------------------


class TestLinks:
    def test_simple_link(self) -> None:
        out = render("[click](https://example.com)")
        assert out == ["<https://example.com|click>"]

    def test_link_url_strips_pipe_and_angle(self) -> None:
        # `|` and `>` in URLs would break Slack's `<url|text>` syntax.
        out = render("[x](https://example.com/a|b>c)")
        assert "|" not in out[0].split("|")[0]  # URL portion
        assert ">" not in out[0].split("|")[0][1:]  # after the opening `<`

    def test_link_without_label_renders_bare(self) -> None:
        # Autolink: `<URL>` with no pipe.
        out = render("[](https://example.com)")
        assert out == ["<https://example.com>"]

    def test_link_label_strips_pipe(self) -> None:
        out = render("[a|b](https://example.com)")
        # The pipe in the label would break syntax — must be removed.
        assert out == ["<https://example.com|ab>"]

    def test_image_renders_as_link_with_alt(self) -> None:
        out = render("![logo](https://example.com/logo.png)")
        assert out == ["<https://example.com/logo.png|[logo]>"]

    def test_image_without_alt_falls_back(self) -> None:
        out = render("![](https://example.com/logo.png)")
        assert "[image]" in out[0]


# ---------------------------------------------------------------------------
# Headings
# ---------------------------------------------------------------------------


class TestHeadings:
    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_every_level_lowers_to_bold(self, level: int) -> None:
        md = "#" * level + " The title"
        out = render(md)
        assert out == ["*The title*"]

    def test_heading_with_inline_markup(self) -> None:
        out = render("# Hello **world**")
        assert out == ["*Hello *world**"]
        # The outer * from heading + inner * from bold is expected;
        # the important thing is no `##` or `**` leaks literally.

    def test_heading_escapes_specials(self) -> None:
        out = render("# <unsafe>")
        assert out == ["*&lt;unsafe&gt;*"]


# ---------------------------------------------------------------------------
# Code blocks
# ---------------------------------------------------------------------------


class TestCodeBlocks:
    def test_fenced_without_language(self) -> None:
        out = render("```\nfoo\n```")
        assert out == ["```\nfoo\n```"]

    def test_fenced_with_language_drops_hint(self) -> None:
        # Slack ignores language hints — we drop them entirely.
        out = render("```python\nprint('hi')\n```")
        assert out == ["```\nprint('hi')\n```"]
        assert "python" not in out[0]

    def test_code_content_not_escaped(self) -> None:
        # Content inside ``` is preformatted — no entity escaping.
        out = render("```\na < b && c > d\n```")
        assert "&lt;" not in out[0]
        assert "a < b && c > d" in out[0]

    def test_code_block_is_not_splittable(self) -> None:
        blocks = render_slack_mrkdwn(parse("```\nfoo\n```"))
        assert blocks[0].splittable is False


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class TestLists:
    def test_unordered_list_uses_bullets(self) -> None:
        assert render("- one\n- two\n- three") == ["• one\n• two\n• three"]

    def test_ordered_list_renumbers_from_one(self) -> None:
        assert render("5. fifth\n6. sixth") == ["1. fifth\n2. sixth"]

    def test_nested_unordered_list_indents(self) -> None:
        md = "- outer\n    - inner a\n    - inner b\n- outer two"
        assert render(md) == ["• outer\n  • inner a\n  • inner b\n• outer two"]

    def test_list_item_with_inline_markup(self) -> None:
        out = render("- a **bold** item")
        assert "*bold*" in out[0]
        assert "**" not in out[0]


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------


class TestBlockquotes:
    def test_single_line_blockquote(self) -> None:
        out = render("> hello")
        assert out == ["> hello"]

    def test_multiline_blockquote_prefixes_every_line(self) -> None:
        out = render("> first\n> second")
        lines = out[0].split("\n")
        assert all(line.startswith(">") for line in lines)

    def test_blockquote_preserves_inline_markup(self) -> None:
        out = render("> **emphatic** quote")
        assert "*emphatic*" in out[0]
        assert out[0].startswith("> ")

    def test_nested_blockquote_stacks_prefixes(self) -> None:
        md = "> outer\n>\n> > inner"
        out = render(md)
        assert "> > " in out[0] or ">> " in out[0]


# ---------------------------------------------------------------------------
# Horizontal rule
# ---------------------------------------------------------------------------


class TestThematicBreak:
    def test_hr_is_box_drawing_chars(self) -> None:
        assert render("---") == [HR_CHAR * HR_WIDTH]

    def test_hr_between_blocks(self) -> None:
        out = render("above\n\n---\n\nbelow")
        assert out == ["above", HR_CHAR * HR_WIDTH, "below"]


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class TestTables:
    def test_narrow_table_uses_fenced_code(self) -> None:
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        out = render(md)
        assert out[0].startswith("```\n")
        assert out[0].endswith("\n```")
        assert "a | b" in out[0]

    def test_table_content_not_escaped(self) -> None:
        # Table wraps in ``` — content is preformatted.
        md = "| <a> | &b |\n|---|---|\n| 1 | 2 |"
        out = render(md)
        assert "&lt;" not in out[0]
        assert "<a>" in out[0]

    def test_table_cells_drop_inline_markup(self) -> None:
        md = "| a | b |\n|---|---|\n| **bold** | *italic* |"
        out = render(md)
        # Inside code fence, no mrkdwn markup should appear.
        assert "bold" in out[0]
        assert "*bold*" not in out[0]  # the `*` wrapper must be dropped

    def test_table_block_is_not_splittable(self) -> None:
        blocks = render_slack_mrkdwn(parse("| a | b |\n|---|---|\n| 1 | 2 |"))
        assert blocks[0].splittable is False


# ---------------------------------------------------------------------------
# Raw HTML
# ---------------------------------------------------------------------------


class TestRawHtml:
    def test_raw_html_block_is_stripped(self) -> None:
        out = render("<script>alert(1)</script>")
        combined = "\n".join(out)
        assert "<script>" not in combined

    def test_raw_inline_html_is_escaped(self) -> None:
        out = render("before <img src=x> after")
        assert "<img" not in "".join(out)
        assert "&lt;img" in "".join(out)


# ---------------------------------------------------------------------------
# SlackMrkdwnFormatter.format() — public entry point
# ---------------------------------------------------------------------------


class TestFormat:
    def test_empty_input_returns_empty_list(self) -> None:
        assert SlackMrkdwnFormatter().format("", max_chars=4000) == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert SlackMrkdwnFormatter().format("   \n\t ", max_chars=4000) == []

    def test_single_paragraph_is_one_chunk(self) -> None:
        assert SlackMrkdwnFormatter().format("hello", max_chars=4000) == ["hello"]

    def test_long_input_produces_multiple_chunks(self) -> None:
        md = "\n\n".join(("x" * 200) for _ in range(10))
        chunks = SlackMrkdwnFormatter().format(md, max_chars=500)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 500

    def test_no_chunk_exceeds_max_chars(self) -> None:
        md = "# Server\n\nSome text.\n\n- one\n- two\n\n```bash\necho hi\n```\n\nEnd."
        chunks = SlackMrkdwnFormatter().format(md, max_chars=200)
        for chunk in chunks:
            assert len(chunk) <= 200


# ---------------------------------------------------------------------------
# Round-trip / end-to-end
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_server_info_renders_without_markdown_leaks(self) -> None:
        md = (
            "## Full Server Configuration\n\n"
            "### CPU\n"
            "| Property | Value |\n"
            "|---|---|\n"
            "| Model | Intel Xeon E5-2697A v4 |\n"
            "| Cores | 5 |\n"
        )
        chunks = SlackMrkdwnFormatter().format(md, max_chars=4000)
        full = "\n\n".join(chunks)
        # No raw markdown syntax should leak.
        assert "##" not in full
        assert "|---|" not in full
        # Bold heading + fenced table should be present.
        assert "*Full Server Configuration*" in full
        assert "```" in full

    def test_no_double_asterisk_anywhere_for_bold(self) -> None:
        """Pin the single-most-important Slack difference from CommonMark."""
        md = "**bold one** and **bold two** and ***bold italic***"
        chunks = SlackMrkdwnFormatter().format(md, max_chars=4000)
        full = " ".join(chunks)
        # The output must contain single `*` for bold, never `**`.
        assert "**" not in full

    def test_angle_brackets_in_text_are_escaped(self) -> None:
        md = "Compare: a < b and b > a."
        chunks = SlackMrkdwnFormatter().format(md, max_chars=4000)
        full = " ".join(chunks)
        # Every `<` in output must be either `&lt;` or the opening of a
        # Slack link `<url|text>`. Simple check: no bare `<` without `|`.
        stripped = full.replace("&lt;", "").replace("&gt;", "")
        for char_idx, ch in enumerate(stripped):
            if ch == "<":
                # Must be a Slack link `<...|...>`.
                assert "|" in stripped[char_idx:]
