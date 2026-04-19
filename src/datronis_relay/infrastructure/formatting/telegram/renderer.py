"""Telegram HTML renderer: mistune AST → list[RenderedBlock].

The renderer is a pure function of the parsed token stream. It produces
a sequence of platform-native `RenderedBlock`s that the chunker packs
into send-ready chunks.

Lowering rules (per roadmap §6.1):

  * Headings         → ``<b>TEXT</b>``
  * Bold / italic    → ``<b>``, ``<i>``
  * Strikethrough    → ``<s>``
  * Inline code      → ``<code>``
  * Fenced code      → ``<pre><code class="language-X">...</code></pre>``
                       (language dropped if not in LANG_WHITELIST)
  * Link             → ``<a href="URL">label</a>``
  * Image            → rendered as link with ``[alt]`` label
                       (Telegram HTML doesn't support inline images)
  * Lists            → plain-text bullets (``• ``) and numbers (``1. ``),
                       indented 2 spaces per nesting level
  * Blockquote       → ``<blockquote>…</blockquote>``
  * Horizontal rule  → 16 U+2500 BOX DRAWINGS LIGHT HORIZONTAL chars
  * Table            → monospace ``<pre>`` block via shared `table.py`
  * Raw HTML blocks  → stripped
  * Raw inline HTML  → HTML-entity-escaped and rendered literally

Every text node passes through `escape_telegram_html` exactly once.
"""

from __future__ import annotations

from typing import Any, cast

from datronis_relay.infrastructure.formatting.chunker import RenderedBlock
from datronis_relay.infrastructure.formatting.escaping import (
    escape_telegram_attr,
    escape_telegram_html,
)
from datronis_relay.infrastructure.formatting.table import render_monospace_table

Token = dict[str, Any]


# ---------------------------------------------------------------------------
# Language whitelist — Telegram's parse_mode=HTML syntax-highlighter accepts
# a limited set of language hints on `<pre><code class="language-...">`.
# Unknown languages are dropped to plain `<pre>` so Telegram doesn't reject
# the message.
# ---------------------------------------------------------------------------

LANG_WHITELIST: frozenset[str] = frozenset(
    {
        "python",
        "javascript",
        "typescript",
        "bash",
        "sh",
        "shell",
        "sql",
        "go",
        "rust",
        "c",
        "cpp",
        "java",
        "kotlin",
        "swift",
        "diff",
        "json",
        "yaml",
        "toml",
        "html",
        "css",
        "xml",
        "ini",
        "dockerfile",
        "makefile",
        "lua",
        "ruby",
        "php",
        "r",
    }
)

# U+2500 BOX DRAWINGS LIGHT HORIZONTAL — used for <hr>.
HR_CHAR = "\u2500"
HR_WIDTH = 16

# Indentation for nested lists (plain-text bullets).
LIST_INDENT = "  "


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_telegram_html(tokens: list[Token]) -> list[RenderedBlock]:
    """Walk `tokens` and emit a list of `RenderedBlock`s.

    Never raises on a known-shape AST. Unknown block types are rendered
    as best-effort inline HTML if they have inline children, else
    silently dropped.
    """
    blocks: list[RenderedBlock] = []
    for token in tokens:
        block = _render_block(token)
        if block is not None:
            blocks.append(block)
    return blocks


# ---------------------------------------------------------------------------
# Block-level handlers
# ---------------------------------------------------------------------------


def _render_block(token: Token) -> RenderedBlock | None:
    t = token.get("type", "")
    if t == "paragraph":
        return _render_paragraph(token)
    if t == "heading":
        return _render_heading(token)
    if t == "block_code":
        return _render_block_code(token)
    if t == "block_quote":
        return _render_block_quote(token)
    if t == "list":
        return _render_list(token, depth=0)
    if t == "thematic_break":
        return RenderedBlock(text=HR_CHAR * HR_WIDTH, splittable=False)
    if t == "table":
        return _render_table(token)
    if t in ("html_block", "blank_line"):
        # Raw HTML blocks are stripped; blank lines are structure only.
        return None
    # Unknown block — best-effort: render children as inline if present.
    children = cast("list[Token]", token.get("children") or [])
    if children:
        inline = _render_inline(children)
        return RenderedBlock(text=inline) if inline.strip() else None
    return None


def _render_paragraph(token: Token) -> RenderedBlock:
    children = cast("list[Token]", token.get("children") or [])
    return RenderedBlock(text=_render_inline(children), splittable=True)


def _render_heading(token: Token) -> RenderedBlock:
    """All heading levels lower to ``<b>TEXT</b>``.

    The roadmap suggests H1/H2 get an extra blank line after; that's
    naturally provided by the chunker's ``\\n\\n`` block separator, so
    we just emit the bold line.
    """
    children = cast("list[Token]", token.get("children") or [])
    text = _render_inline(children)
    return RenderedBlock(text=f"<b>{text}</b>", splittable=True)


def _render_block_code(token: Token) -> RenderedBlock:
    raw = cast(str, token.get("raw", "")).rstrip("\n")
    info = cast(str, (token.get("attrs") or {}).get("info", "") or "")
    lang = info.strip().split()[0].lower() if info.strip() else ""
    escaped = escape_telegram_html(raw)
    if lang in LANG_WHITELIST:
        html = f'<pre><code class="language-{lang}">{escaped}</code></pre>'
    else:
        html = f"<pre>{escaped}</pre>"
    # Code blocks must never be split — an unclosed ``</pre>`` would
    # break the Telegram parser on the next chunk.
    return RenderedBlock(text=html, splittable=False)


def _render_block_quote(token: Token) -> RenderedBlock:
    """Render ``<blockquote>…</blockquote>`` around the combined inner text."""
    inner_lines: list[str] = []
    for child in cast("list[Token]", token.get("children") or []):
        t = child.get("type", "")
        if t == "paragraph":
            children = cast("list[Token]", child.get("children") or [])
            inner_lines.append(_render_inline(children))
        elif t == "block_quote":
            # Nested blockquote — include its wrapped HTML verbatim.
            nested = _render_block_quote(child)
            inner_lines.append(nested.text)
        else:
            sub = _render_block(child)
            if sub is not None:
                inner_lines.append(sub.text)
    inner = "\n".join(line for line in inner_lines if line)
    return RenderedBlock(text=f"<blockquote>{inner}</blockquote>", splittable=False)


def _render_list(token: Token, depth: int) -> RenderedBlock:
    """Render a list as plain-text bullets/numbers with nested indentation.

    Ordered lists always restart numbering at 1 — CommonMark convention
    and simpler than tracking the ``start`` attribute across partially
    rendered lists (which mistune doesn't expose anyway).
    """
    attrs = token.get("attrs") or {}
    ordered = bool(attrs.get("ordered", False))
    lines: list[str] = []
    for idx, item in enumerate(cast("list[Token]", token.get("children") or []), start=1):
        number = idx if ordered else None
        lines.extend(_render_list_item(item, depth, number))
    return RenderedBlock(text="\n".join(lines), splittable=True)


def _render_list_item(
    token: Token,
    depth: int,
    number: int | None,
) -> list[str]:
    """Render one list item to one-or-more plain-text lines."""
    indent = LIST_INDENT * depth
    marker = f"{number}." if number is not None else "•"
    prefix = f"{indent}{marker} "

    primary_parts: list[str] = []
    nested_lines: list[str] = []
    for child in cast("list[Token]", token.get("children") or []):
        t = child.get("type", "")
        if t in ("block_text", "paragraph"):
            inline = _render_inline(cast("list[Token]", child.get("children") or []))
            if inline:
                primary_parts.append(inline)
        elif t == "list":
            nested_block = _render_list(child, depth=depth + 1)
            nested_lines.extend(nested_block.text.split("\n"))

    primary_text = " ".join(primary_parts).strip()
    result: list[str] = []
    if primary_text:
        result.append(f"{prefix}{primary_text}")
    else:
        result.append(prefix.rstrip())
    result.extend(nested_lines)
    return result


def _render_table(token: Token) -> RenderedBlock:
    rows = _extract_table_rows(token)
    if not rows:
        return RenderedBlock(text="", splittable=False)
    grid = render_monospace_table(rows)
    escaped = escape_telegram_html(grid)
    return RenderedBlock(text=f"<pre>{escaped}</pre>", splittable=False)


def _extract_table_rows(token: Token) -> list[list[str]]:
    rows: list[list[str]] = []
    for section in cast("list[Token]", token.get("children") or []):
        section_type = section.get("type", "")
        if section_type == "table_head":
            # `table_head` contains the header cells directly (no wrapper row).
            cells = _extract_row_cells(section)
            if cells:
                rows.append(cells)
        elif section_type == "table_body":
            for row_token in cast("list[Token]", section.get("children") or []):
                if row_token.get("type") == "table_row":
                    cells = _extract_row_cells(row_token)
                    if cells:
                        rows.append(cells)
    return rows


def _extract_row_cells(row_or_head: Token) -> list[str]:
    cells: list[str] = []
    for cell in cast("list[Token]", row_or_head.get("children") or []):
        if cell.get("type") == "table_cell":
            cell_children = cast("list[Token]", cell.get("children") or [])
            cells.append(_render_table_cell_text(cell_children))
    return cells


def _render_table_cell_text(tokens: list[Token]) -> str:
    """Flatten inline markup to plain text for a table cell.

    Telegram won't render HTML markup inside ``<pre>``, so tables drop
    bold/italic/code/link styling and just concatenate visible text.
    Multiple whitespace characters are collapsed to a single space.
    """
    parts: list[str] = []
    for token in tokens:
        t = token.get("type", "")
        if t in ("text", "codespan"):
            parts.append(cast(str, token.get("raw", "")))
        elif t in ("strong", "emphasis", "strikethrough", "link"):
            inner = _render_table_cell_text(
                cast("list[Token]", token.get("children") or [])
            )
            parts.append(inner)
        elif t == "image":
            inner = _render_table_cell_text(
                cast("list[Token]", token.get("children") or [])
            )
            parts.append(inner or "image")
        elif t in ("linebreak", "softbreak"):
            parts.append(" ")
        elif t in ("html_inline", "inline_html"):
            # Preserve user content as literal text — the surrounding
            # `<pre>` wrapper HTML-escapes the entire cell string, so
            # e.g. `<a>` renders as `&lt;a&gt;` in Telegram instead of
            # silently disappearing. (mistune uses both names depending
            # on context: `html_inline` in paragraphs, `inline_html`
            # inside table cells.)
            parts.append(cast(str, token.get("raw", "")))
    text = "".join(parts)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Inline handlers
# ---------------------------------------------------------------------------


def _render_inline(tokens: list[Token]) -> str:
    """Render a sequence of inline tokens to a single string."""
    return "".join(_render_inline_one(t) for t in tokens)


def _render_inline_one(token: Token) -> str:
    t = token.get("type", "")
    if t == "text":
        return escape_telegram_html(cast(str, token.get("raw", "")))
    if t == "strong":
        return f"<b>{_render_inline(_children(token))}</b>"
    if t == "emphasis":
        return f"<i>{_render_inline(_children(token))}</i>"
    if t == "strikethrough":
        return f"<s>{_render_inline(_children(token))}</s>"
    if t == "codespan":
        return f"<code>{escape_telegram_html(cast(str, token.get('raw', '')))}</code>"
    if t == "link":
        return _render_link(token)
    if t == "image":
        return _render_image(token)
    if t in ("linebreak", "softbreak"):
        return "\n"
    if t in ("html_inline", "inline_html"):
        # Strip raw inline HTML by rendering it as escaped literal text.
        # mistune uses both names depending on context.
        return escape_telegram_html(cast(str, token.get("raw", "")))
    # Unknown inline — prefer raw, else recurse into children.
    raw = token.get("raw")
    if isinstance(raw, str):
        return escape_telegram_html(raw)
    children = token.get("children")
    if isinstance(children, list):
        return _render_inline(cast("list[Token]", children))
    return ""


def _render_link(token: Token) -> str:
    attrs = token.get("attrs") or {}
    url = escape_telegram_attr(cast(str, attrs.get("url", "")))
    label = _render_inline(_children(token)).strip() or url
    return f'<a href="{url}">{label}</a>'


def _render_image(token: Token) -> str:
    # Telegram HTML doesn't support inline images — render as a link
    # with the alt text wrapped in brackets so it's obvious.
    attrs = token.get("attrs") or {}
    url = escape_telegram_attr(cast(str, attrs.get("url", "")))
    alt = _render_inline(_children(token)).strip() or "image"
    return f'<a href="{url}">[{alt}]</a>'


def _children(token: Token) -> list[Token]:
    return cast("list[Token]", token.get("children") or [])
