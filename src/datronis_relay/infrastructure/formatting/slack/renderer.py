"""Slack mrkdwn renderer: mistune AST → list[RenderedBlock].

Lowering rules (per roadmap §6.2):

  * Headings         → ``*TEXT*`` (bold line — Slack has no heading syntax)
  * Bold             → ``*TEXT*`` (**single** asterisk — NOT CommonMark ``**``)
  * Italic           → ``_TEXT_``
  * Strikethrough    → ``~TEXT~`` (single tilde)
  * Inline code      → `` `TEXT` `` (no escape inside — Slack treats code as
                       preformatted)
  * Fenced code      → ```` ``` ````\\n...\\n```` ``` ```` (language hints
                       dropped — Slack ignores them)
  * Link             → ``<URL|label>`` (Slack's own syntax, NOT markdown's
                       ``[label](URL)``)
  * Image            → rendered as link with ``[alt]`` label
  * Lists            → same as Telegram: plain-text ``•`` / ``1.`` bullets
  * Blockquote       → every line prefixed with ``> ``
  * Horizontal rule  → 16 U+2500 chars (same as Telegram)
  * Table            → monospace grid wrapped in ```` ``` ```` fence
  * Raw HTML blocks  → stripped
  * Raw inline HTML  → Slack-escaped and rendered literally

Text escaping: only ``<``, ``>``, ``&`` need escaping (``&lt;`` etc.).
Content inside code (inline or fenced) is **not** escaped — Slack
treats code as preformatted and does not parse markup or links there.
"""

from __future__ import annotations

from typing import Any, cast

from datronis_relay.infrastructure.formatting.chunker import RenderedBlock
from datronis_relay.infrastructure.formatting.escaping import (
    escape_slack_text,
    escape_slack_url,
)
from datronis_relay.infrastructure.formatting.table import render_monospace_table

Token = dict[str, Any]

HR_CHAR = "\u2500"
HR_WIDTH = 16
LIST_INDENT = "  "


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render_slack_mrkdwn(tokens: list[Token]) -> list[RenderedBlock]:
    """Walk `tokens` and emit a list of `RenderedBlock`s for Slack mrkdwn."""
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
        return None
    children = cast("list[Token]", token.get("children") or [])
    if children:
        inline = _render_inline(children)
        return RenderedBlock(text=inline) if inline.strip() else None
    return None


def _render_paragraph(token: Token) -> RenderedBlock:
    children = cast("list[Token]", token.get("children") or [])
    return RenderedBlock(text=_render_inline(children), splittable=True)


def _render_heading(token: Token) -> RenderedBlock:
    """All heading levels lower to ``*TEXT*`` (Slack bold).

    Slack has no native heading syntax. A bold line on its own is the
    best approximation. The chunker's ``\\n\\n`` block separator provides
    the visual gap after the heading.
    """
    children = cast("list[Token]", token.get("children") or [])
    text = _render_inline(children)
    return RenderedBlock(text=f"*{text}*", splittable=True)


def _render_block_code(token: Token) -> RenderedBlock:
    """Fenced code → triple-backtick block.

    Slack ignores language hints on code fences, so we drop them.
    Content inside code fences is NOT escaped — Slack treats it as
    preformatted and won't parse markup or links.
    """
    raw = cast(str, token.get("raw", "")).rstrip("\n")
    return RenderedBlock(text=f"```\n{raw}\n```", splittable=False)


def _render_block_quote(token: Token) -> RenderedBlock:
    """Render as ``> `` prefix on every line.

    For nested blockquotes, the inner blockquote already has ``> ``
    prefixes, so the outer adds another layer → ``> > inner``. Slack
    only renders a single quote depth visually, but the nesting is at
    least visible as a structural cue.
    """
    inner_lines: list[str] = []
    for child in cast("list[Token]", token.get("children") or []):
        t = child.get("type", "")
        if t == "paragraph":
            children = cast("list[Token]", child.get("children") or [])
            inner_lines.append(_render_inline(children))
        elif t == "block_quote":
            nested = _render_block_quote(child)
            inner_lines.append(nested.text)
        else:
            sub = _render_block(child)
            if sub is not None:
                inner_lines.append(sub.text)
    inner = "\n".join(line for line in inner_lines if line)
    prefixed = "\n".join(
        f"> {line}" if line else ">" for line in inner.split("\n")
    )
    return RenderedBlock(text=prefixed, splittable=False)


def _render_list(token: Token, depth: int) -> RenderedBlock:
    attrs = token.get("attrs") or {}
    ordered = bool(attrs.get("ordered", False))
    lines: list[str] = []
    for idx, item in enumerate(
        cast("list[Token]", token.get("children") or []), start=1
    ):
        number = idx if ordered else None
        lines.extend(_render_list_item(item, depth, number))
    return RenderedBlock(text="\n".join(lines), splittable=True)


def _render_list_item(
    token: Token,
    depth: int,
    number: int | None,
) -> list[str]:
    indent = LIST_INDENT * depth
    marker = f"{number}." if number is not None else "•"
    prefix = f"{indent}{marker} "

    primary_parts: list[str] = []
    nested_lines: list[str] = []
    for child in cast("list[Token]", token.get("children") or []):
        t = child.get("type", "")
        if t in ("block_text", "paragraph"):
            inline = _render_inline(
                cast("list[Token]", child.get("children") or [])
            )
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
    """Render table as a monospace grid inside a triple-backtick fence.

    Cell content is plain text (no markup — Slack won't render mrkdwn
    inside code fences). The grid is NOT escaped because triple-backtick
    content is preformatted.
    """
    rows = _extract_table_rows(token)
    if not rows:
        return RenderedBlock(text="", splittable=False)
    grid = render_monospace_table(rows)
    return RenderedBlock(text=f"```\n{grid}\n```", splittable=False)


def _extract_table_rows(token: Token) -> list[list[str]]:
    rows: list[list[str]] = []
    for section in cast("list[Token]", token.get("children") or []):
        section_type = section.get("type", "")
        if section_type == "table_head":
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
    """Flatten inline markup to plain text for a table cell."""
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
            parts.append(cast(str, token.get("raw", "")))
    text = "".join(parts)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Inline handlers
# ---------------------------------------------------------------------------


def _render_inline(tokens: list[Token]) -> str:
    return "".join(_render_inline_one(t) for t in tokens)


def _render_inline_one(token: Token) -> str:
    t = token.get("type", "")
    if t == "text":
        return escape_slack_text(cast(str, token.get("raw", "")))
    if t == "strong":
        return f"*{_render_inline(_children(token))}*"
    if t == "emphasis":
        return f"_{_render_inline(_children(token))}_"
    if t == "strikethrough":
        return f"~{_render_inline(_children(token))}~"
    if t == "codespan":
        # No escape inside inline code — Slack treats it as preformatted.
        return f"`{cast(str, token.get('raw', ''))}`"
    if t == "link":
        return _render_link(token)
    if t == "image":
        return _render_image(token)
    if t in ("linebreak", "softbreak"):
        return "\n"
    if t in ("html_inline", "inline_html"):
        return escape_slack_text(cast(str, token.get("raw", "")))
    raw = token.get("raw")
    if isinstance(raw, str):
        return escape_slack_text(raw)
    children = token.get("children")
    if isinstance(children, list):
        return _render_inline(cast("list[Token]", children))
    return ""


def _render_link(token: Token) -> str:
    """Render as ``<URL|label>`` — Slack's own link syntax."""
    attrs = token.get("attrs") or {}
    url = escape_slack_url(cast(str, attrs.get("url", "")))
    label = _render_inline(_children(token)).strip()
    if not label:
        return f"<{url}>"
    # Strip pipe from label so it doesn't break <url|text> syntax.
    label = label.replace("|", "")
    return f"<{url}|{label}>"


def _render_image(token: Token) -> str:
    attrs = token.get("attrs") or {}
    url = escape_slack_url(cast(str, attrs.get("url", "")))
    alt = _render_inline(_children(token)).strip() or "image"
    alt = alt.replace("|", "")
    return f"<{url}|[{alt}]>"


def _children(token: Token) -> list[Token]:
    return cast("list[Token]", token.get("children") or [])
