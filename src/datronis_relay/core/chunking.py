from __future__ import annotations

# Telegram hard limit is 4096 codepoints. Leave margin for the continuation
# marker and any adapter-level prefixes.
DEFAULT_LIMIT = 4000
CONTINUATION_MARKER = "\n\n▼ continued"


def chunk_message(text: str, limit: int = DEFAULT_LIMIT) -> list[str]:
    """Split a long message into chunks, preferring newline boundaries.

    Guarantees:
      - each chunk ≤ `limit` codepoints
      - the continuation marker is appended to every chunk except the last
      - if the input fits in one chunk, the marker is never added
      - splits on the last newline before the effective limit when one exists
    """
    if limit <= len(CONTINUATION_MARKER) + 10:
        raise ValueError("limit is too small for safe chunking")
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    effective_limit = limit - len(CONTINUATION_MARKER)

    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, effective_limit)
        if split_at <= 0:
            split_at = effective_limit
        head = remaining[:split_at].rstrip()
        chunks.append(head + CONTINUATION_MARKER)
        remaining = remaining[split_at:].lstrip("\n")

    chunks.append(remaining)
    return chunks
