from __future__ import annotations

import pytest

from datronis_relay.core.interval_parser import (
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    format_interval,
    parse_interval,
)


class TestParseInterval:
    def test_seconds(self) -> None:
        assert parse_interval("30s") == 30

    def test_minutes(self) -> None:
        assert parse_interval("5m") == 300

    def test_hours(self) -> None:
        assert parse_interval("2h") == 7200

    def test_days(self) -> None:
        assert parse_interval("1d") == 86400

    def test_case_insensitive(self) -> None:
        assert parse_interval("2H") == 7200

    def test_tolerates_whitespace(self) -> None:
        assert parse_interval("  5m  ") == 300

    def test_below_min_rejected(self) -> None:
        with pytest.raises(ValueError, match="too short"):
            parse_interval(f"{MIN_INTERVAL_SECONDS - 1}s")

    def test_above_max_rejected(self) -> None:
        with pytest.raises(ValueError, match="too long"):
            parse_interval(f"{MAX_INTERVAL_SECONDS + 1}s")

    @pytest.mark.parametrize("bad", ["", "abc", "5", "5 minutes", "-1h", "1y", "m5", "5mm"])
    def test_invalid_formats(self, bad: str) -> None:
        with pytest.raises(ValueError, match="invalid interval"):
            parse_interval(bad)


class TestFormatInterval:
    def test_days(self) -> None:
        assert format_interval(86_400) == "1d"

    def test_two_days(self) -> None:
        assert format_interval(172_800) == "2d"

    def test_hours(self) -> None:
        assert format_interval(3_600) == "1h"

    def test_minutes(self) -> None:
        assert format_interval(300) == "5m"

    def test_seconds_fallback(self) -> None:
        # 90s doesn't divide cleanly into minutes: falls back to seconds
        assert format_interval(90) == "90s"

    def test_round_trip(self) -> None:
        for text in ("30s", "5m", "2h", "1d"):
            assert format_interval(parse_interval(text)) == text
