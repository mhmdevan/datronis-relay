"""Thin typed wrapper around `mistune.create_markdown(renderer="ast")`.

Isolating the mistune import in a single module means:

  - Every other formatting module uses a stable typed shape, not the raw
    library types (which evolve between minor releases).
  - `test_formatting_markdown_ast.py` is the *only* place that needs to
    update when mistune changes its AST shape.
  - The concrete renderers (Phase M-1/M-2) import `parse()` from here
    and never see `mistune` directly.

The returned AST is a flat list of block-level token dicts. Each token
has:

    { "type": str, "children": list[Token] | None, "raw": str | None, "attrs": dict[str, Any] | None, ... }

The exact fields vary by token type (see mistune docs). The type names
we care about for Phase M-1 are: `paragraph`, `heading`, `block_code`,
`block_quote`, `list`, `list_item`, `thematic_break`, `table`,
`table_head`, `table_body`, `table_row`, `table_cell`, plus inline
types `text`, `strong`, `emphasis`, `codespan`, `link`, `image`,
`strikethrough`.
"""

from __future__ import annotations

from typing import Any

import mistune

Token = dict[str, Any]


_markdown = mistune.create_markdown(
    renderer="ast",
    plugins=["strikethrough", "table"],
)


def parse(text: str) -> list[Token]:
    """Parse CommonMark + GFM (tables, strikethrough) text into an AST token list.

    Returns an empty list for empty / whitespace-only input. Never raises
    on well-formed markdown; malformed fragments (e.g. an unclosed `<a>`
    tag inside text) are emitted as `html_inline` / `html_block` tokens
    rather than causing a parse error.

    The caller is responsible for handling any token type the renderers
    don't yet support (typically by falling through to `text` extraction).
    """
    if not text or not text.strip():
        return []
    result = _markdown(text)
    # mistune's ast renderer returns list[dict]; defensive narrowing
    # in case a future version returns a tuple or single dict.
    if isinstance(result, list):
        return result
    return []
