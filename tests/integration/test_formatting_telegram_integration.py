"""Integration tests for the end-to-end Telegram HTML formatter.

These exercise the full pipeline: parse → render → chunk against
realistic long Claude-style responses. The goal is to catch issues
that unit tests on individual token types miss — tag balance across
blocks, chunk boundaries splitting at the right places, total chunk
count staying reasonable.
"""

from __future__ import annotations

import pytest

from datronis_relay.infrastructure.formatting import TelegramHtmlFormatter

# Realistic Claude response: this is the kind of output that motivated
# the whole formatting roadmap. Headings, tables, code, lists, quotes.
SERVER_DIAGNOSTIC = """\
## Server Diagnostic Report

### System Overview

| Metric         | Value                                   |
|----------------|-----------------------------------------|
| Hostname       | prod-web-1                              |
| Uptime         | 14 days, 3 hours                        |
| Load average   | 0.87, 0.62, 0.54                        |

### Recent Errors

I found **3 error clusters** in the last 24 hours:

1. **Database connection timeouts** — 47 occurrences between 03:12 and 03:28 UTC.
2. **Nginx 502 responses** — clustered around the same window.
3. **Disk space warning** — `/var/log` reached 87% full.

### Root cause hypothesis

The timeline strongly suggests a cascade:

> The database connection pool was saturated because a long-running
> backup job held connections for ~16 minutes. Nginx returned 502
> while waiting for upstream responses.

### Recommended fix

```bash
# On prod-web-1, check the backup job's connection pattern:
sudo journalctl -u postgres-backup --since "1 day ago" | grep -i "connection"

# If the backup is the culprit, move it off-peak:
sudo systemctl edit postgres-backup
# Add: [Timer] OnCalendar=*-*-* 04:00:00
```

Let me know if you want me to run the fix.
"""


class TestRealisticResponses:
    def test_diagnostic_response_fits_in_few_chunks(self) -> None:
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=4000
        )
        # A typical response should fit in 1-3 chunks. A sudden jump to
        # 10+ is a regression worth investigating.
        assert 1 <= len(chunks) <= 3

    def test_every_chunk_respects_max_chars(self) -> None:
        for max_chars in (500, 1000, 4000):
            chunks = TelegramHtmlFormatter().format(
                SERVER_DIAGNOSTIC, max_chars=max_chars
            )
            for chunk in chunks:
                assert len(chunk) <= max_chars

    def test_tags_are_balanced_within_every_chunk(self) -> None:
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=4000
        )
        for chunk in chunks:
            _assert_tags_balanced(chunk)

    def test_pre_blocks_are_never_split(self) -> None:
        # If a `<pre>` opens in one chunk, its `</pre>` must be in the
        # same chunk — otherwise Telegram rejects the message.
        for max_chars in (500, 1000, 2000, 4000):
            chunks = TelegramHtmlFormatter().format(
                SERVER_DIAGNOSTIC, max_chars=max_chars
            )
            for chunk in chunks:
                assert chunk.count("<pre>") == chunk.count("</pre>"), (
                    f"unbalanced <pre> in chunk at max_chars={max_chars}"
                )

    def test_no_raw_markdown_leaks_into_any_chunk(self) -> None:
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=4000
        )
        combined = "\n".join(chunks)
        assert "##" not in combined
        assert "**" not in combined
        assert "|---|" not in combined

    def test_headings_became_bold(self) -> None:
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=4000
        )
        combined = "\n".join(chunks)
        assert "<b>Server Diagnostic Report</b>" in combined
        assert "<b>System Overview</b>" in combined

    def test_table_renders_as_monospace_pre(self) -> None:
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=4000
        )
        combined = "\n".join(chunks)
        assert "<pre>" in combined
        # The table's header row should be alignable.
        assert "Metric" in combined
        assert "Hostname" in combined

    def test_code_block_preserves_language_hint(self) -> None:
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=4000
        )
        combined = "\n".join(chunks)
        assert '<pre><code class="language-bash">' in combined

    @pytest.mark.parametrize("max_chars", [1000, 2000, 4000])
    def test_robust_across_chunk_sizes(self, max_chars: int) -> None:
        """At every realistic Telegram chunk limit, output is well-formed.

        Telegram's actual hard limit is 4096; `channel.max_message_length`
        is 4000. We also exercise 2000 and 1000 to catch issues that only
        surface when multi-chunk splitting kicks in.

        Limits below 1000 expose a known Phase M-3 edge case: a single
        fenced code block that exceeds `max_chars` gets hard-wrapped
        mid-content, producing unbalanced `<pre>` tags. Phase M-3 adds
        per-block line-level splitting with ``(part i/n)`` labels.
        """
        chunks = TelegramHtmlFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=max_chars
        )
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.strip()  # no empty chunks
            assert len(chunk) <= max_chars
            _assert_tags_balanced(chunk)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_BALANCED_TAGS = ("b", "i", "s", "u", "code", "pre", "blockquote")


def _assert_tags_balanced(text: str) -> None:
    """Rough balance check: every `<X>` in _BALANCED_TAGS has a matching `</X>`.

    Does not parse the full HTML (that'd require BeautifulSoup) — but the
    paired-tag count check catches the kinds of bugs Telegram's parser
    cares about (unclosed `<pre>`, orphan `</code>`, etc.).
    """
    for tag in _BALANCED_TAGS:
        opens = text.count(f"<{tag}>")
        # For <pre><code class="..."> there's an open tag with attributes —
        # count all `<pre` and `</pre>` instead for the pre tag.
        if tag == "pre":
            opens = text.count("<pre>")  # opened without attributes
        if tag == "code":
            # count both `<code>` and `<code class="...">`
            opens = text.count("<code>") + text.count("<code ")
        if tag == "a":
            opens = text.count("<a ") + text.count("<a>")
        closes = text.count(f"</{tag}>")
        assert opens == closes, (
            f"unbalanced <{tag}>: {opens} opens, {closes} closes in\n{text[:500]}"
        )
