"""Unit tests for the shared monospace table helper.

Both Telegram (M-1) and Slack (M-2) lower markdown tables to the same
primitive — a monospace grid wrapped in a `<pre>` or ``` ``` ```
container. These tests pin the grid itself; container-wrapping lives
in the platform renderer.
"""

from __future__ import annotations

from datronis_relay.infrastructure.formatting.table import (
    CELL_SEPARATOR,
    DEFAULT_MAX_WIDTH,
    HEADER_SEPARATOR,
    render_monospace_table,
    render_vertical_table,
)


class TestHorizontalMode:
    def test_empty_input_returns_empty_string(self) -> None:
        assert render_monospace_table([]) == ""

    def test_single_row_no_header_separator(self) -> None:
        # With only one row there's nothing to underline.
        assert render_monospace_table([["a", "b"]]) == "a | b"

    def test_two_row_table_has_header_separator(self) -> None:
        out = render_monospace_table([["A", "B"], ["1", "2"]])
        assert out == "A | B\n--+--\n1 | 2"

    def test_pads_shorter_rows_with_empty_cells(self) -> None:
        out = render_monospace_table([["A", "B", "C"], ["1"]])
        # Row 2 should have been padded to 3 cells.
        lines = out.split("\n")
        assert lines[0] == "A | B | C"
        assert lines[-1].startswith("1 ")

    def test_column_widths_match_longest_cell(self) -> None:
        out = render_monospace_table([["A", "B"], ["long value", "x"]])
        lines = out.split("\n")
        # Header cell "A" padded to width of "long value" (10 chars).
        assert lines[0] == "A          | B"

    def test_strips_cell_whitespace(self) -> None:
        out = render_monospace_table([["  A ", " B "], ["1", "2"]])
        assert "A" in out
        assert "B" in out
        # Leading/trailing whitespace on headers should be gone.
        assert out.splitlines()[0] == "A | B"

    def test_header_separator_matches_column_widths(self) -> None:
        out = render_monospace_table([["Hi", "Hello"], ["1", "2"]])
        sep = out.splitlines()[1]
        # col_widths = [2, 5]; separator is `-+-` (dash on each side of `+`)
        # so row = "-"*2 + "-+-" + "-"*5 = "---+------" (3 dashes, +, 6 dashes).
        assert sep == "---+------"

    def test_trailing_spaces_are_stripped(self) -> None:
        out = render_monospace_table([["A", "B"], ["1", "2"]])
        for line in out.splitlines():
            assert not line.endswith(" "), f"{line!r} has trailing spaces"


class TestVerticalFallback:
    def test_wide_table_falls_through_to_vertical(self) -> None:
        # Force a wide value by making a long cell.
        rows = [["Property", "Value"], ["Name", "x" * 80]]
        out = render_monospace_table(rows, max_width=60)
        # Vertical mode emits "header: value" lines.
        assert "Property: Name" in out
        assert "Value: " in out
        # And it does NOT contain the horizontal separator row.
        assert HEADER_SEPARATOR not in out

    def test_horizontal_picked_when_just_under_max_width(self) -> None:
        # 10-char cols plus separator = 10 + 3 + 10 = 23 chars. Well under 60.
        rows = [["Header A  ", "Header B  "], ["row A", "row B"]]
        out = render_monospace_table(rows, max_width=60)
        assert HEADER_SEPARATOR in out

    def test_default_max_width_is_60(self) -> None:
        assert DEFAULT_MAX_WIDTH == 60

    def test_multi_record_vertical_has_blank_lines_between_blocks(self) -> None:
        out = render_vertical_table(
            [["Day", "Cost"], ["Mon", "$1"], ["Tue", "$2"]]
        )
        # Expect blocks separated by a blank line.
        assert "\n\n" in out

    def test_single_row_vertical_is_pipe_joined(self) -> None:
        # There's no "value" to map headers to — render as joined row.
        assert render_vertical_table([["a", "b", "c"]]) == "a | b | c"

    def test_empty_vertical_returns_empty_string(self) -> None:
        assert render_vertical_table([]) == ""

    def test_vertical_skips_fully_empty_pairs(self) -> None:
        # A record row with an all-empty cell should not emit a `: ` line.
        out = render_vertical_table([["A", ""], ["1", ""]])
        assert ": " not in out or out.count(": ") == 1  # only A:1


class TestEdgeCases:
    def test_cell_separator_constant_shape(self) -> None:
        # The API contract: separator is `" | "` (3 chars).
        assert CELL_SEPARATOR == " | "
        assert len(CELL_SEPARATOR) == 3

    def test_unicode_cell_content_doesnt_crash(self) -> None:
        # Emoji / CJK widths aren't handled (documented limitation)
        # but the renderer must not raise.
        out = render_monospace_table([["日本語", "⚙️"], ["a", "b"]])
        assert "日本語" in out
        assert "⚙️" in out

    def test_row_with_all_empty_cells_still_produces_a_line(self) -> None:
        out = render_monospace_table([["A", "B"], ["", ""]])
        # Two rows of output, plus header separator.
        lines = out.split("\n")
        assert len(lines) == 3
