"""Unit tests for the mistune AST wrapper.

These tests pin the shape of the AST we rely on in Phase M-1. If
`mistune` ever changes a `type` name or token structure, a test in
here fails loudly and we update the renderers in one place.
"""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.markdown_ast import parse


class TestEmptyInput:
    def test_empty_string_returns_empty_list(self) -> None:
        assert parse("") == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        assert parse("  \n\n\t  ") == []


class TestBasicTokenTypes:
    def test_heading(self) -> None:
        tokens = parse("# title")
        assert tokens[0]["type"] == "heading"
        assert tokens[0]["attrs"]["level"] == 1

    def test_multiple_heading_levels(self) -> None:
        tokens = parse("# H1\n## H2\n### H3")
        levels = [t["attrs"]["level"] for t in tokens if t["type"] == "heading"]
        assert levels == [1, 2, 3]

    def test_paragraph(self) -> None:
        tokens = parse("just some text")
        assert tokens[0]["type"] == "paragraph"

    def test_blank_line_separates_paragraphs(self) -> None:
        tokens = parse("first\n\nsecond")
        paragraphs = [t for t in tokens if t["type"] == "paragraph"]
        assert len(paragraphs) == 2

    def test_fenced_code_preserves_info_string(self) -> None:
        tokens = parse("```python\nprint('hi')\n```")
        block = tokens[0]
        assert block["type"] == "block_code"
        # info field names vary across mistune versions — check both
        info = block.get("attrs", {}).get("info") or block.get("info")
        assert info == "python"

    def test_unordered_list(self) -> None:
        tokens = parse("- one\n- two\n- three")
        assert tokens[0]["type"] == "list"
        assert tokens[0]["attrs"]["ordered"] is False

    def test_ordered_list(self) -> None:
        tokens = parse("1. one\n2. two")
        assert tokens[0]["type"] == "list"
        assert tokens[0]["attrs"]["ordered"] is True

    def test_blockquote(self) -> None:
        tokens = parse("> quoted line")
        assert tokens[0]["type"] == "block_quote"

    def test_thematic_break(self) -> None:
        tokens = parse("some text\n\n---\n\nmore text")
        types = [t["type"] for t in tokens]
        assert "thematic_break" in types


class TestInlineMarkup:
    def test_strong_emphasis_token_in_paragraph_children(self) -> None:
        tokens = parse("a **bold** b")
        paragraph = tokens[0]
        child_types = [c["type"] for c in paragraph["children"]]
        assert "strong" in child_types

    def test_emphasis_token_in_paragraph_children(self) -> None:
        tokens = parse("a *italic* b")
        paragraph = tokens[0]
        child_types = [c["type"] for c in paragraph["children"]]
        assert "emphasis" in child_types

    def test_codespan_token_in_paragraph_children(self) -> None:
        tokens = parse("run `ls -la` now")
        paragraph = tokens[0]
        child_types = [c["type"] for c in paragraph["children"]]
        assert "codespan" in child_types

    def test_link_token_in_paragraph_children(self) -> None:
        tokens = parse("see [here](https://example.com)")
        paragraph = tokens[0]
        child_types = [c["type"] for c in paragraph["children"]]
        assert "link" in child_types


class TestPluginTokens:
    def test_strikethrough_plugin_is_enabled(self) -> None:
        tokens = parse("a ~~strike~~ b")
        paragraph = tokens[0]
        child_types = [c["type"] for c in paragraph["children"]]
        assert "strikethrough" in child_types

    def test_table_plugin_is_enabled(self) -> None:
        tokens = parse("| a | b |\n|---|---|\n| 1 | 2 |")
        assert tokens[0]["type"] == "table"


class TestRobustness:
    def test_never_raises_on_malformed_input(self) -> None:
        # mistune is permissive — these should not throw.
        parse("**unclosed bold")
        parse("| a | b\nno closing pipe")
        parse("```\nunclosed fence")
        parse("[text](unclosed-paren")

    def test_returns_list_type_always(self) -> None:
        assert isinstance(parse("hello"), list)
        assert isinstance(parse(""), list)
