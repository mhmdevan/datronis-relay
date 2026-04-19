"""Long code-block splitter with ``(part i/n)`` labels.

When Claude returns a 200-line script, the rendered code block
(wrapped in ``<pre>`` or ` ``` `) may exceed the platform's chunk
limit. Feeding it to the chunker as a single ``splittable=False``
block causes a hard-wrap, producing orphaned tags.

This module splits the raw code content at **line boundaries**, then
re-wraps each piece with fresh platform fences and a ``(part i/n)``
label so the user knows the code continues in the next message.

Usage (inside a platform renderer):

    blocks = split_code_block(
        raw_code=raw,
        max_chars=max_chars,
        wrap_fn=lambda code, label: f'<pre>{esc(code)} {label}</pre>',
    )

The returned blocks are already ``RenderedBlock(splittable=False)`` and
safe to feed directly to ``chunk_blocks()``.
"""

from __future__ import annotations

from collections.abc import Callable

from datronis_relay.infrastructure.formatting.chunker import RenderedBlock


def split_code_block(
    raw_code: str,
    max_chars: int,
    wrap_fn: Callable[[str, str], str],
    *,
    overhead_margin: int = 60,
) -> list[RenderedBlock]:
    """Split a long code block into multiple wrapped, labelled blocks.

    Args:
        raw_code: The raw code content (already escaped if needed by the
            caller — this function doesn't escape).
        max_chars: The platform chunk limit.
        wrap_fn: ``wrap_fn(code_content, part_label) -> str``. Produces
            the fully wrapped block string (e.g. ``<pre>...</pre>`` or
            ````` ``` ... ``` `````). ``part_label`` is ``""`` when the
            code fits in a single block, ``"(part 1/3)"`` etc. otherwise.
        overhead_margin: Extra chars reserved for the wrapper + label.
            Defaults to 60 which is generous for both platforms.

    Returns:
        A list of ``RenderedBlock(splittable=False)`` instances. If the
        code fits in one block, the list has one element with no label.
    """
    # Check if the whole thing fits in one block.
    single = wrap_fn(raw_code, "")
    if len(single) <= max_chars:
        return [RenderedBlock(text=single, splittable=False)]

    # Budget per part: max_chars minus wrapper/label overhead.
    budget = max(max_chars - overhead_margin, max_chars // 2)

    # Split raw code into line-bounded parts that each fit in `budget`.
    parts = _split_lines_into_parts(raw_code, budget)
    total = len(parts)

    blocks: list[RenderedBlock] = []
    for i, part in enumerate(parts, start=1):
        label = f"(part {i}/{total})"
        wrapped = wrap_fn(part, label)
        blocks.append(RenderedBlock(text=wrapped, splittable=False))
    return blocks


def _split_lines_into_parts(text: str, budget: int) -> list[str]:
    """Split `text` at line boundaries so each part is ≤ `budget` chars.

    If a single line exceeds the budget, it's included alone in its own
    part (the wrapper will still fit within max_chars because we reserved
    overhead_margin).
    """
    lines = text.split("\n")
    parts: list[str] = []
    current_lines: list[str] = []
    current_len = 0

    for line in lines:
        # +1 for the newline that will join them.
        line_len = len(line) + (1 if current_lines else 0)
        if current_len + line_len > budget and current_lines:
            parts.append("\n".join(current_lines))
            current_lines = []
            current_len = 0
        current_lines.append(line)
        current_len += line_len

    if current_lines:
        parts.append("\n".join(current_lines))

    return parts
