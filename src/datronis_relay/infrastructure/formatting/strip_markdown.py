"""Best-effort markdown syntax stripper for the parse-error fallback path.

When `mistune.parse()` throws (rare, but not impossible on adversarial
input), the formatter falls back to this function instead of sending raw
``##`` / ``**`` / ``|---|`` to the user.

The stripping is deliberately aggressive: it's better to lose a bold
marker than to leak raw syntax. The user already gets a degraded
experience (no rich formatting); leaking markdown artifacts on top of
that makes it look broken.

The function is **pure** — no I/O, no state, no imports beyond stdlib
``re``. Designed to be unit-tested exhaustively.
"""

from __future__ import annotations

import re

# Fenced code blocks: ```lang\n...\n``` or ~~~lang\n...\n~~~
# We keep the content but drop the fences and language hint.
_FENCED_CODE_RE = re.compile(
    r"^(`{3,}|~{3,})[^\n]*\n(.*?)\n\1\s*$",
    re.MULTILINE | re.DOTALL,
)

# ATX headings: # through ######
_HEADING_RE = re.compile(r"^#{1,6}\s+", re.MULTILINE)

# Bold / italic / bold-italic markers (** __ *** ___)
_BOLD_ITALIC_RE = re.compile(r"(\*{1,3}|_{1,3})")

# Strikethrough ~~text~~
_STRIKE_RE = re.compile(r"~~")

# Inline code backticks (single or double)
_INLINE_CODE_RE = re.compile(r"`{1,2}")

# GFM table separator rows: |---|---|  or  | :---: | ---: |
_TABLE_SEP_RE = re.compile(r"^\|?[\s:]*-{3,}[\s:]*(\|[\s:]*-{3,}[\s:]*)*\|?\s*$", re.MULTILINE)

# Leading/trailing pipes on table data rows: | cell | cell |
_TABLE_PIPE_RE = re.compile(r"^\||\|$", re.MULTILINE)

# Horizontal rules: ---, ***, ___ (three or more, alone on a line)
_HR_RE = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)

# Link / image syntax: [text](url) or ![alt](url)
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")

# Blockquote markers: > at the start of a line
_BLOCKQUOTE_RE = re.compile(r"^>\s?", re.MULTILINE)


def strip_markdown(text: str) -> str:
    """Remove common markdown syntax, keeping the visible text.

    The output is plain text suitable for escaping and chunking. It is
    NOT intended to be pretty — it's the "least-bad" fallback when the
    real renderer can't run.

    Stripping order matters:
      1. Fenced code blocks (remove fences, keep content)
      2. Links / images (keep label, drop URL)
      3. Headings (drop ``#`` markers)
      4. Bold / italic / strikethrough markers
      5. Inline code backticks
      6. Table separator rows (drop entirely)
      7. Table leading/trailing pipes
      8. Horizontal rules (replace with blank line)
      9. Blockquote markers (drop ``>``)
     10. Collapse runs of blank lines to a single blank line
    """
    if not text:
        return ""

    result = text

    # 1. Fenced code: keep content, drop fences + language hint
    result = _FENCED_CODE_RE.sub(r"\2", result)

    # 2. Links / images: keep the label text
    result = _LINK_RE.sub(r"\1", result)

    # 3. Headings
    result = _HEADING_RE.sub("", result)

    # 4. Bold / italic markers
    result = _BOLD_ITALIC_RE.sub("", result)

    # 5. Strikethrough
    result = _STRIKE_RE.sub("", result)

    # 6. Inline code backticks
    result = _INLINE_CODE_RE.sub("", result)

    # 7. Table separator rows
    result = _TABLE_SEP_RE.sub("", result)

    # 8. Table leading/trailing pipes
    result = _TABLE_PIPE_RE.sub("", result)

    # 9. Horizontal rules → blank line
    result = _HR_RE.sub("", result)

    # 10. Blockquote markers
    result = _BLOCKQUOTE_RE.sub("", result)

    # 11. Collapse blank-line runs
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
