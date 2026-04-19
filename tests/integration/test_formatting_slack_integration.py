"""Integration tests for the end-to-end Slack mrkdwn formatter.

Parallel to `test_formatting_telegram_integration.py`. These exercise
the full pipeline: parse -> render -> chunk against a realistic mixed-
element Claude response. The goal is to catch issues that unit tests on
individual token types miss -- fence balance, chunk boundaries, total
chunk count, and the critical "no double asterisk" invariant.
"""

from __future__ import annotations

import pytest

from datronis_relay.infrastructure.formatting import SlackMrkdwnFormatter

# Same realistic Claude response used in the Telegram integration test.
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

1. **Database connection timeouts** -- 47 occurrences between 03:12 and 03:28 UTC.
2. **Nginx 502 responses** -- clustered around the same window.
3. **Disk space warning** -- `/var/log` reached 87% full.

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
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        # A typical response should fit in 1-3 chunks.
        assert 1 <= len(chunks) <= 3

    def test_every_chunk_respects_max_chars(self) -> None:
        for max_chars in (500, 1000, 4000):
            chunks = SlackMrkdwnFormatter().format(
                SERVER_DIAGNOSTIC, max_chars=max_chars
            )
            for chunk in chunks:
                assert len(chunk) <= max_chars

    def test_code_fences_balanced_within_every_chunk(self) -> None:
        """Every triple-backtick open must have a matching close in the same chunk."""
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        for chunk in chunks:
            assert chunk.count("```") % 2 == 0, (
                f"unbalanced ``` in chunk:\n{chunk[:300]}"
            )

    def test_no_raw_markdown_leaks(self) -> None:
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        assert "##" not in combined
        assert "|---|" not in combined

    def test_no_double_asterisk_anywhere(self) -> None:
        """THE critical Slack invariant: bold is *x*, never **x**."""
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        assert "**" not in combined

    def test_headings_became_slack_bold(self) -> None:
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        assert "*Server Diagnostic Report*" in combined
        assert "*System Overview*" in combined

    def test_table_wrapped_in_code_fence(self) -> None:
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        assert "```" in combined
        assert "Metric" in combined
        assert "Hostname" in combined

    def test_code_block_drops_language_hint(self) -> None:
        """Slack ignores language hints -- they must not appear in output."""
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        # The input has ```bash -- "bash" must be dropped, code kept.
        assert "sudo journalctl" in combined
        # The word "bash" shouldn't appear as a standalone first line after ```.
        for chunk in chunks:
            lines = chunk.split("\n")
            for i, line in enumerate(lines):
                if line.strip() == "```" and i + 1 < len(lines):
                    # The line after ``` must NOT be just a language identifier.
                    next_line = lines[i + 1].strip()
                    assert next_line != "bash", "language hint 'bash' leaked"

    def test_blockquote_uses_angle_bracket_prefix(self) -> None:
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        # At least one line should start with `> `.
        assert any(
            line.startswith("> ") for line in combined.split("\n")
        ), "no `> ` blockquote prefix found"

    def test_ordered_list_uses_plain_text_numbers(self) -> None:
        chunks = SlackMrkdwnFormatter().format(SERVER_DIAGNOSTIC, max_chars=4000)
        combined = "\n".join(chunks)
        assert "1. " in combined
        assert "2. " in combined
        assert "3. " in combined

    @pytest.mark.parametrize("max_chars", [1000, 2000, 4000])
    def test_robust_across_chunk_sizes(self, max_chars: int) -> None:
        """At every realistic chunk limit, output is well-formed.

        Limits below 1000 expose the same Phase M-3 oversized-block
        edge case documented in the Telegram integration test.
        """
        chunks = SlackMrkdwnFormatter().format(
            SERVER_DIAGNOSTIC, max_chars=max_chars
        )
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.strip()  # no empty chunks
            assert len(chunk) <= max_chars
            # Fence balance within each chunk.
            assert chunk.count("```") % 2 == 0, (
                f"unbalanced ``` at max_chars={max_chars}"
            )
