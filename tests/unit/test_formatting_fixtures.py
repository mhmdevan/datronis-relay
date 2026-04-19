"""Golden-fixture test harness.

Phase M-0: asserted every `tests/fixtures/markdown/*.md` file parses
to a non-empty AST.

Phase M-1: also compares the rendered Telegram HTML output against a
hand-verified `*.telegram.html` side file.

Phase M-2 (this file as of now): also compares the rendered Slack
mrkdwn output against `*.slack.txt` side files. A mismatch means
either (a) the renderer changed and the committer needs to update
the side file after reviewing the diff, or (b) a real regression.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from datronis_relay.infrastructure.formatting import (
    SlackMrkdwnFormatter,
    TelegramHtmlFormatter,
)
from datronis_relay.infrastructure.formatting.markdown_ast import parse

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "markdown"
CHUNK_BOUNDARY = "\n<!-- CHUNK BOUNDARY -->\n"


def _fixture_paths() -> list[Path]:
    """All .md fixtures (including whitespace-only edge cases)."""
    return sorted(p for p in FIXTURE_DIR.glob("*.md") if p.name != "README.md")


# Fixtures that are expected to produce non-empty AST (excludes
# whitespace-only and similar edge cases whose correct output is []).
_WHITESPACE_ONLY = {"13_whitespace.md"}


def _content_fixture_paths() -> list[Path]:
    """Fixtures with real markdown content (non-empty AST expected)."""
    return [p for p in _fixture_paths() if p.name not in _WHITESPACE_ONLY]


def test_at_least_fourteen_fixtures_exist() -> None:
    # Guard against accidental deletion — Phase M-3 added 4 more (≥ 14).
    assert len(_fixture_paths()) >= 14, (
        f"Expected ≥ 14 markdown fixtures, found {len(_fixture_paths())} "
        f"in {FIXTURE_DIR}"
    )


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_parses_to_non_empty_ast(fixture: Path) -> None:
    """Every content fixture must produce a non-empty token list."""
    text = fixture.read_text(encoding="utf-8")
    tokens = parse(text)
    assert tokens, f"{fixture.name} parsed to an empty AST"


def test_whitespace_fixture_parses_to_empty_ast() -> None:
    """The whitespace-only fixture must produce an empty AST — by design."""
    ws_path = FIXTURE_DIR / "13_whitespace.md"
    assert ws_path.exists()
    tokens = parse(ws_path.read_text(encoding="utf-8"))
    assert tokens == []


def test_whitespace_fixture_produces_empty_chunks() -> None:
    """Both formatters return [] for whitespace-only input."""
    ws_text = (FIXTURE_DIR / "13_whitespace.md").read_text(encoding="utf-8")
    assert TelegramHtmlFormatter().format(ws_text, max_chars=4000) == []
    assert SlackMrkdwnFormatter().format(ws_text, max_chars=4000) == []


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_ast_tokens_have_type_field(fixture: Path) -> None:
    """Every token (top level and nested) must carry a non-empty `type`."""
    text = fixture.read_text(encoding="utf-8")
    tokens = parse(text)
    for token in _walk(tokens):
        assert "type" in token, f"{fixture.name}: token missing 'type': {token}"
        assert token["type"], f"{fixture.name}: token has empty 'type': {token}"


def _walk(tokens: list[dict]) -> list[dict]:
    """Depth-first walk yielding every token in an AST."""
    result: list[dict] = []
    for token in tokens:
        result.append(token)
        children = token.get("children")
        if isinstance(children, list):
            result.extend(_walk(children))
    return result


# ---------------------------------------------------------------------------
# Phase M-1: Telegram HTML golden assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_telegram_golden_output(fixture: Path) -> None:
    """Every fixture input must produce the exact expected Telegram HTML.

    The expected output lives alongside the input with a `.telegram.html`
    extension. Regenerate the file with::

        PYTHONPATH=src python3.11 scripts/regenerate_telegram_goldens.py

    Or by running the `tests/fixtures/markdown/README.md` instructions.
    If the diff is intentional (e.g. you changed a rendering rule),
    review and commit the new expected file.
    """
    expected_path = fixture.with_suffix(".telegram.html")
    if not expected_path.exists():
        pytest.skip(f"no expected output yet for {fixture.name}")

    text = fixture.read_text(encoding="utf-8")
    chunks = TelegramHtmlFormatter().format(text, max_chars=4000)
    actual = CHUNK_BOUNDARY.join(chunks) + "\n"
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"{fixture.name}: rendered Telegram HTML differs from "
        f"{expected_path.name}.\n"
        f"--- expected ---\n{expected}\n--- actual ---\n{actual}"
    )


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_telegram_output_has_no_leaked_markdown(fixture: Path) -> None:
    """The user's complaint was raw `##` / `|---|` leaking to Telegram.

    Every fixture's rendered output must be free of those literals —
    they belong in the input, not the output.
    """
    text = fixture.read_text(encoding="utf-8")
    chunks = TelegramHtmlFormatter().format(text, max_chars=4000)
    full = "\n".join(chunks)
    assert "##" not in full, f"{fixture.name}: raw `##` leaked into output"
    assert "|---|" not in full, f"{fixture.name}: raw `|---|` leaked into output"
    # Also: `**bold**` syntax must be gone — lowered to `<b>`.
    assert "**" not in full, f"{fixture.name}: raw `**` leaked into output"


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_telegram_chunks_respect_limit(fixture: Path) -> None:
    """Every rendered chunk must be ≤ the platform char limit."""
    text = fixture.read_text(encoding="utf-8")
    chunks = TelegramHtmlFormatter().format(text, max_chars=4000)
    for chunk in chunks:
        assert len(chunk) <= 4000, (
            f"{fixture.name}: chunk exceeds 4000 chars ({len(chunk)})"
        )


# ---------------------------------------------------------------------------
# Phase M-2: Slack mrkdwn golden assertions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_slack_golden_output(fixture: Path) -> None:
    """Every fixture input must produce the exact expected Slack mrkdwn."""
    expected_path = fixture.with_suffix(".slack.txt")
    if not expected_path.exists():
        pytest.skip(f"no expected output yet for {fixture.name}")

    text = fixture.read_text(encoding="utf-8")
    chunks = SlackMrkdwnFormatter().format(text, max_chars=4000)
    actual = CHUNK_BOUNDARY.join(chunks) + "\n"
    expected = expected_path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"{fixture.name}: rendered Slack mrkdwn differs from "
        f"{expected_path.name}.\n"
        f"--- expected ---\n{expected}\n--- actual ---\n{actual}"
    )


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_slack_output_has_no_leaked_markdown(fixture: Path) -> None:
    """No raw CommonMark syntax should appear in the Slack output."""
    text = fixture.read_text(encoding="utf-8")
    chunks = SlackMrkdwnFormatter().format(text, max_chars=4000)
    full = "\n".join(chunks)
    assert "##" not in full, f"{fixture.name}: raw `##` leaked into Slack output"
    assert "|---|" not in full, f"{fixture.name}: raw `|---|` leaked into Slack output"


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_slack_has_no_double_asterisk(fixture: Path) -> None:
    """THE critical Slack invariant: bold must be *x*, never **x**."""
    text = fixture.read_text(encoding="utf-8")
    chunks = SlackMrkdwnFormatter().format(text, max_chars=4000)
    full = "\n".join(chunks)
    assert "**" not in full, (
        f"{fixture.name}: double-asterisk `**` leaked — "
        f"Slack bold is `*x*`, not `**x**`"
    )


@pytest.mark.parametrize("fixture", _content_fixture_paths(), ids=lambda p: p.stem)
def test_fixture_slack_chunks_respect_limit(fixture: Path) -> None:
    """Every rendered chunk must be ≤ the platform char limit."""
    text = fixture.read_text(encoding="utf-8")
    chunks = SlackMrkdwnFormatter().format(text, max_chars=4000)
    for chunk in chunks:
        assert len(chunk) <= 4000, (
            f"{fixture.name}: Slack chunk exceeds 4000 chars ({len(chunk)})"
        )
