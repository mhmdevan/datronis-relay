"""Monospace table rendering — shared by every platform formatter.

Both Telegram and Slack lower markdown tables to the same primitive: a
plain-text grid wrapped in a monospace container (`<pre>` on Telegram,
triple-backtick fence on Slack). This module owns the grid layout so
both adapters share the logic.

Two modes:

* **Horizontal** (default) — cells laid out in columns with ``" | "``
  separators and a dash row under the header. Used when the total table
  width fits within ``max_width``.
* **Vertical** (fallback) — each body row expanded into one
  ``header: value`` line per cell, with a blank line between records.
  Used when the horizontal layout would be wider than ``max_width`` —
  this matters for mobile readability, where 40-column terminals are
  common.

Known limitation (acceptable for Phase M-1): cell widths are measured
in codepoints, not display cells. A cell containing an emoji or CJK
character misaligns by one or two columns in monospace fonts. Fixing
this needs `unicodedata.east_asian_width()` or the `wcwidth` library;
tracked as a Phase M-3 polish item.
"""

from __future__ import annotations

DEFAULT_MAX_WIDTH = 60
"""Default horizontal width threshold. Tables wider than this fall
through to the vertical layout. 60 chars is a compromise between
mobile readability (~40 chars portrait) and desktop comfort.
"""

HEADER_SEPARATOR = "-+-"
CELL_SEPARATOR = " | "


def render_monospace_table(
    rows: list[list[str]],
    max_width: int = DEFAULT_MAX_WIDTH,
) -> str:
    """Render `rows` as a monospace text table.

    The first row is treated as the header — a dash row is inserted
    below it and the data rows follow. If the computed horizontal
    width exceeds ``max_width``, falls back to ``render_vertical_table``
    automatically.

    Empty `rows` returns an empty string. A single-row input produces
    just that row with no separator (there is no header to underline).
    """
    if not rows:
        return ""

    normalized = _normalize(rows)
    col_widths = _col_widths(normalized)
    total_width = sum(col_widths) + (len(col_widths) - 1) * len(CELL_SEPARATOR)

    if total_width > max_width:
        return render_vertical_table(normalized)

    lines: list[str] = []
    for i, row in enumerate(normalized):
        padded = [cell.ljust(col_widths[c]) for c, cell in enumerate(row)]
        lines.append(CELL_SEPARATOR.join(padded).rstrip())
        if i == 0 and len(normalized) > 1:
            lines.append(HEADER_SEPARATOR.join("-" * w for w in col_widths))

    return "\n".join(lines)


def render_vertical_table(rows: list[list[str]]) -> str:
    """Vertical ``header: value`` fallback for tables too wide to fit.

    - A single row is emitted as a pipe-joined line (nothing to expand).
    - Multiple rows: each data row becomes a block of ``header: value``
      pairs, with a blank line between blocks.
    - Empty cells on the value side are omitted (the header line is
      still emitted if the header itself is non-empty; a fully-empty
      pair is skipped).
    """
    if not rows:
        return ""

    normalized = _normalize(rows)
    if len(normalized) == 1:
        return CELL_SEPARATOR.join(normalized[0]).rstrip()

    headers = normalized[0]
    blocks: list[str] = []
    for record in normalized[1:]:
        record_lines: list[str] = []
        for h, v in zip(headers, record, strict=False):
            if not h and not v:
                continue
            record_lines.append(f"{h}: {v}")
        if record_lines:
            blocks.append("\n".join(record_lines))

    return "\n\n".join(blocks)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize(rows: list[list[str]]) -> list[list[str]]:
    """Strip whitespace and pad short rows with empty cells."""
    if not rows:
        return []
    num_cols = max(len(r) for r in rows)
    return [
        [cell.strip() for cell in row] + [""] * (num_cols - len(row))
        for row in rows
    ]


def _col_widths(rows: list[list[str]]) -> list[int]:
    """Return the max codepoint width of each column across all rows."""
    if not rows:
        return []
    num_cols = len(rows[0])
    return [max(len(row[c]) for row in rows) for c in range(num_cols)]
