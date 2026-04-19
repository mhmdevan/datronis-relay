"""Unit tests for the Telegram HTML renderer + formatter.

Organized by token type — one test class per concern. These pin the
lowering rules from roadmap §6.1 and guard the "zero unescaped `<`"
invariant that keeps Telegram's parse_mode=HTML parser happy.
"""

from __future__ import annotations

import pytest

from datronis_relay.infrastructure.formatting import TelegramHtmlFormatter
from datronis_relay.infrastructure.formatting.markdown_ast import parse
from datronis_relay.infrastructure.formatting.telegram.renderer import (
    HR_CHAR,
    HR_WIDTH,
    LANG_WHITELIST,
    render_telegram_html,
)


def render(md: str) -> list[str]:
    """Parse + render helper: returns the block texts as strings."""
    return [b.text for b in render_telegram_html(parse(md))]


# ---------------------------------------------------------------------------
# Inline markup
# ---------------------------------------------------------------------------


class TestInlineMarkup:
    def test_plain_text_passes_through_escaped(self) -> None:
        assert render("hello world") == ["hello world"]

    def test_strong_becomes_b_tag(self) -> None:
        assert render("**bold**") == ["<b>bold</b>"]

    def test_emphasis_becomes_i_tag(self) -> None:
        assert render("*italic*") == ["<i>italic</i>"]

    def test_strikethrough_becomes_s_tag(self) -> None:
        assert render("~~struck~~") == ["<s>struck</s>"]

    def test_codespan_becomes_code_tag(self) -> None:
        assert render("run `ls -la` now") == ["run <code>ls -la</code> now"]

    def test_codespan_escapes_html_specials(self) -> None:
        # `<` inside inline code must become `&lt;`.
        assert render("use `<tag>`") == ["use <code>&lt;tag&gt;</code>"]

    def test_mixed_inline_nests_correctly(self) -> None:
        out = render("***bold italic***")
        assert "<b>" in out[0] and "</b>" in out[0]
        assert "<i>" in out[0] and "</i>" in out[0]

    def test_angle_brackets_in_text_are_escaped(self) -> None:
        assert render("before <script> after") == ["before &lt;script&gt; after"]

    def test_ampersand_in_text_is_escaped(self) -> None:
        assert render("a & b") == ["a &amp; b"]


# ---------------------------------------------------------------------------
# Links and images
# ---------------------------------------------------------------------------


class TestLinks:
    def test_simple_link(self) -> None:
        out = render("[click](https://example.com)")
        assert out == ['<a href="https://example.com">click</a>']

    def test_link_url_escapes_ampersand(self) -> None:
        out = render("[x](https://example.com/?a=1&b=2)")
        assert '&amp;' in out[0]
        assert 'href="https://example.com/?a=1&amp;b=2"' in out[0]

    def test_link_url_escapes_quotes(self) -> None:
        # Defensive: an unescaped `"` in href would close the attribute
        # and break the Telegram parser.
        out = render('[x](https://example.com/?a="b")')
        assert '"' not in out[0].split('href="')[1].split('"')[0].split(">")[0]

    def test_link_label_with_markup(self) -> None:
        out = render("[**bold**](https://example.com)")
        assert '<a href="https://example.com"><b>bold</b></a>' in out[0]

    def test_image_renders_as_link_with_alt(self) -> None:
        out = render("![logo](https://example.com/logo.png)")
        assert out == ['<a href="https://example.com/logo.png">[logo]</a>']

    def test_image_without_alt_falls_back_to_placeholder(self) -> None:
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
        assert out == ["<b>The title</b>"]

    def test_heading_with_inline_markup(self) -> None:
        out = render("# Hello **world**")
        assert out == ["<b>Hello <b>world</b></b>"]

    def test_heading_escapes_html_specials(self) -> None:
        out = render("# <unsafe>")
        assert out == ["<b>&lt;unsafe&gt;</b>"]


# ---------------------------------------------------------------------------
# Code blocks
# ---------------------------------------------------------------------------


class TestCodeBlocks:
    def test_fenced_without_language_is_plain_pre(self) -> None:
        out = render("```\nfoo\n```")
        assert out == ["<pre>foo</pre>"]

    def test_fenced_with_whitelisted_language_adds_code_class(self) -> None:
        out = render("```python\nprint('hi')\n```")
        assert out == ['<pre><code class="language-python">print(\'hi\')</code></pre>']

    def test_fenced_with_unknown_language_drops_to_plain_pre(self) -> None:
        out = render("```jetlang\ncode here\n```")
        # "jetlang" is not in the whitelist.
        assert out == ["<pre>code here</pre>"]

    def test_language_is_lowercased_before_lookup(self) -> None:
        out = render("```PYTHON\nx\n```")
        assert '<pre><code class="language-python">' in out[0]

    def test_code_content_escapes_html_specials(self) -> None:
        out = render("```html\n<div>&amp;</div>\n```")
        assert "&lt;div&gt;" in out[0]
        # The `&` inside the already-escaped `&amp;` in input is treated as
        # three literal chars: `&`, `a`, etc. The `&` gets escaped again.
        assert "&amp;amp;" in out[0]

    def test_every_language_in_whitelist_is_lowercase(self) -> None:
        # The whitelist must be all-lowercase; matching lowercases input.
        for lang in LANG_WHITELIST:
            assert lang == lang.lower()

    def test_common_whitelisted_languages(self) -> None:
        for lang in ("python", "javascript", "bash", "json", "sql"):
            assert lang in LANG_WHITELIST


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


class TestLists:
    def test_unordered_list_uses_bullets(self) -> None:
        out = render("- one\n- two\n- three")
        assert out == ["• one\n• two\n• three"]

    def test_ordered_list_renumbers_from_one(self) -> None:
        # CommonMark always renumbers — even if the source starts at 5.
        out = render("5. fifth\n6. sixth")
        assert out == ["1. fifth\n2. sixth"]

    def test_nested_unordered_list_indents(self) -> None:
        md = "- outer\n    - inner a\n    - inner b\n- outer two"
        out = render(md)
        assert out == ["• outer\n  • inner a\n  • inner b\n• outer two"]

    def test_nested_ordered_list_indents(self) -> None:
        md = "1. outer\n    1. inner\n2. outer two"
        out = render(md)
        assert "• inner" not in out[0]  # nested ordered list stays ordered
        assert "  1. inner" in out[0]

    def test_list_item_with_inline_markup(self) -> None:
        out = render("- a **bold** item")
        assert "<b>bold</b>" in out[0]


# ---------------------------------------------------------------------------
# Blockquotes
# ---------------------------------------------------------------------------


class TestBlockquotes:
    def test_single_line_blockquote(self) -> None:
        out = render("> hello")
        assert out == ["<blockquote>hello</blockquote>"]

    def test_multiline_blockquote_joins_lines_with_newline(self) -> None:
        # Softbreak between quote lines renders as `\n`, which Telegram
        # displays as a line break inside the blockquote.
        out = render("> first\n> second")
        assert out == ["<blockquote>first\nsecond</blockquote>"]

    def test_blockquote_preserves_inline_markup(self) -> None:
        out = render("> **emphatic** quote")
        assert "<b>emphatic</b>" in out[0]
        assert out[0].startswith("<blockquote>")
        assert out[0].endswith("</blockquote>")


# ---------------------------------------------------------------------------
# Horizontal rule
# ---------------------------------------------------------------------------


class TestThematicBreak:
    def test_hr_is_box_drawing_chars(self) -> None:
        out = render("---")
        assert out == [HR_CHAR * HR_WIDTH]

    def test_hr_between_blocks(self) -> None:
        out = render("above\n\n---\n\nbelow")
        assert out == ["above", HR_CHAR * HR_WIDTH, "below"]


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------


class TestTables:
    def test_narrow_table_uses_horizontal_pre(self) -> None:
        md = "| a | b |\n|---|---|\n| 1 | 2 |"
        out = render(md)
        assert out[0].startswith("<pre>")
        assert out[0].endswith("</pre>")
        # Cells rendered as plain text.
        assert "a | b" in out[0]
        assert "1 | 2" in out[0]

    def test_table_content_is_html_escaped(self) -> None:
        md = "| <a> | &b |\n|---|---|\n| 1 | 2 |"
        out = render(md)
        # The raw `<a>` in the cell must not leak into the <pre>.
        assert "&lt;a&gt;" in out[0]
        assert "&amp;" in out[0]

    def test_wide_table_falls_through_to_vertical(self) -> None:
        md = (
            "| Property | Value |\n|---|---|\n"
            "| Model | Intel Xeon E5-2697A v4 @ 2.60GHz (8 cores, 16 threads) |"
        )
        out = render(md)
        # Vertical format emits "header: value" pairs — no `-+-` separator.
        assert "-+-" not in out[0]
        assert "Property: Model" in out[0]

    def test_table_cells_drop_inline_markup(self) -> None:
        # Tables render inside <pre>; Telegram won't show inner HTML.
        md = "| a | b |\n|---|---|\n| **bold** | *italic* |"
        out = render(md)
        assert "<b>" not in out[0]
        assert "<i>" not in out[0]

    def test_table_block_is_not_splittable(self) -> None:
        # Splitting a <pre>...</pre> across chunks would orphan a tag.
        blocks = render_telegram_html(parse("| a | b |\n|---|---|\n| 1 | 2 |"))
        assert blocks[0].splittable is False


# ---------------------------------------------------------------------------
# Raw HTML / security-adjacent
# ---------------------------------------------------------------------------


class TestRawHtml:
    def test_raw_html_block_is_stripped(self) -> None:
        # mistune treats a `<script>` block as html_block — we drop it.
        out = render("<script>alert(1)</script>")
        # Either empty or escaped-text fallback; never an executable <script>.
        combined = "\n".join(out)
        assert "<script>" not in combined
        assert "</script>" not in combined

    def test_raw_inline_html_is_escaped(self) -> None:
        out = render("before <img src=x> after")
        # `<img>` must be rendered as literal, not as HTML.
        assert "<img" not in "".join(out)
        assert "&lt;img" in "".join(out)


# ---------------------------------------------------------------------------
# TelegramHtmlFormatter.format() — the public entry point
# ---------------------------------------------------------------------------


class TestFormat:
    def test_empty_input_returns_empty_list(self) -> None:
        assert TelegramHtmlFormatter().format("", max_chars=4000) == []

    def test_whitespace_only_input_returns_empty_list(self) -> None:
        assert TelegramHtmlFormatter().format("   \n\t ", max_chars=4000) == []

    def test_single_paragraph_is_one_chunk(self) -> None:
        chunks = TelegramHtmlFormatter().format("hello world", max_chars=4000)
        assert chunks == ["hello world"]

    def test_long_input_produces_multiple_chunks(self) -> None:
        # 10 paragraphs of 200 chars each = 2000+ chars; should split at
        # max_chars=500 into multiple chunks.
        md = "\n\n".join(("x" * 200) for _ in range(10))
        chunks = TelegramHtmlFormatter().format(md, max_chars=500)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 500

    def test_no_chunk_exceeds_max_chars(self) -> None:
        # Realistic mixed-element input.
        md = (
            "# Server\n\n"
            "Some context paragraph.\n\n"
            "- first item\n- second item\n- third item\n\n"
            "```python\nprint('hello')\n```\n\n"
            "A final line."
        )
        chunks = TelegramHtmlFormatter().format(md, max_chars=200)
        for chunk in chunks:
            assert len(chunk) <= 200

    def test_returns_str_list(self) -> None:
        chunks = TelegramHtmlFormatter().format("# title\n\nbody", max_chars=4000)
        assert isinstance(chunks, list)
        assert all(isinstance(c, str) for c in chunks)


# ---------------------------------------------------------------------------
# Round-trip / end-to-end
# ---------------------------------------------------------------------------


class TestRoundTrip:
    def test_server_info_example_from_roadmap_renders_cleanly(self) -> None:
        md = (
            "## Full Server Configuration\n\n"
            "### CPU\n"
            "| Property | Value |\n"
            "|---|---|\n"
            "| Model | Intel Xeon E5-2697A v4 |\n"
            "| Cores | 5 |\n"
        )
        chunks = TelegramHtmlFormatter().format(md, max_chars=4000)
        full = "\n\n".join(chunks)
        # The user's complaint was raw `##` and `|---|` leaking. Both
        # must be gone in the output.
        assert "##" not in full
        assert "|---|" not in full
        # And the bold / pre tags are present.
        assert "<b>Full Server Configuration</b>" in full
        assert "<pre>" in full

    def test_no_unescaped_angle_brackets_in_plain_text(self) -> None:
        # A paragraph with a `<` in the text must not produce an unescaped
        # `<` in the output (Telegram would reject the whole message).
        md = "Compare: a < b and b > a."
        chunks = TelegramHtmlFormatter().format(md, max_chars=4000)
        full = " ".join(chunks)
        # Every `<` in the rendered output must start a known HTML tag.
        # A cheap test: replace every known tag with empty, then count `<`.
        stripped = full
        for tag in ("<b>", "</b>", "<i>", "</i>", "<s>", "</s>",
                    "<code>", "</code>", "<pre>", "</pre>",
                    "<a ", "</a>", "<blockquote>", "</blockquote>"):
            stripped = stripped.replace(tag, "")
        # Whatever `<` remains must be the escaped entity prefix.
        assert "<" not in stripped
