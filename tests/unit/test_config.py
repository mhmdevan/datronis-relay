"""Tests for `infrastructure/config.py` — YAML loader, env overrides,
pydantic validation, and the `json` field alias."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from datronis_relay.infrastructure.config import AppConfig


def _write_yaml(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body)
    return path


MINIMAL_YAML = """
telegram:
  bot_token: "123456:ABCDEF"

users:
  - id: "telegram:1"
    display_name: "Me"
    allowed_tools: ["Read"]
    rate_limit:
      per_minute: 20
      per_day: 1000
"""


class TestLoadMinimalConfig:
    def test_happy_path(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        config = AppConfig.load(path)

        assert config.telegram.enabled is True
        assert config.telegram.bot_token.get_secret_value() == "123456:ABCDEF"
        assert len(config.users) == 1
        assert config.users[0].id == "telegram:1"
        assert config.users[0].allowed_tools == ["Read"]
        assert config.users[0].rate_limit.per_minute == 20

    def test_defaults_are_applied(self, tmp_path: Path) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        config = AppConfig.load(path)

        assert config.slack.enabled is False
        assert config.scheduler.enabled is True
        assert config.attachments.enabled is True
        assert config.logging.level == "INFO"
        assert config.logging.json_output is True
        assert config.metrics.enabled is False
        assert config.claude.model == "claude-sonnet-4-6"


class TestFileNotFound:
    def test_missing_file_raises(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.yaml"
        with pytest.raises(FileNotFoundError, match="config file not found"):
            AppConfig.load(missing)


class TestRootShape:
    def test_non_dict_root_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("- just\n- a\n- list\n")
        with pytest.raises(ValueError, match="config root must be a mapping"):
            AppConfig.load(path)

    def test_empty_file_falls_back_to_empty_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("")
        # Empty YAML → empty dict → missing required `telegram` → ValidationError
        with pytest.raises(ValidationError):
            AppConfig.load(path)


class TestEnvOverrides:
    def test_telegram_token_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        monkeypatch.setenv("DATRONIS_TELEGRAM_BOT_TOKEN", "999:OVERRIDE")
        config = AppConfig.load(path)
        assert config.telegram.bot_token.get_secret_value() == "999:OVERRIDE"

    def test_slack_bot_token_env_enables_slack(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        monkeypatch.setenv("DATRONIS_SLACK_BOT_TOKEN", "xoxb-env")
        monkeypatch.setenv("DATRONIS_SLACK_APP_TOKEN", "xapp-env")
        config = AppConfig.load(path)
        assert config.slack.enabled is True
        assert config.slack.bot_token.get_secret_value() == "xoxb-env"
        assert config.slack.app_token.get_secret_value() == "xapp-env"

    def test_log_level_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        monkeypatch.setenv("DATRONIS_LOG_LEVEL", "DEBUG")
        config = AppConfig.load(path)
        assert config.logging.level == "DEBUG"

    @pytest.mark.parametrize(
        "env_value,expected",
        [("true", True), ("false", False), ("1", True), ("0", False), ("yes", True)],
    )
    def test_log_json_override_parses_truthy_values(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        env_value: str,
        expected: bool,
    ) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        monkeypatch.setenv("DATRONIS_LOG_JSON", env_value)
        config = AppConfig.load(path)
        assert config.logging.json_output is expected

    def test_config_path_env_is_consulted_when_no_path_given(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_yaml(tmp_path, MINIMAL_YAML)
        monkeypatch.setenv("DATRONIS_CONFIG_PATH", str(path))
        # Note: we pass path=None so the env var is used
        config = AppConfig.load()
        assert config.users[0].id == "telegram:1"


class TestJsonFieldAlias:
    def test_yaml_key_is_json_python_attribute_is_json_output(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            MINIMAL_YAML + "\nlogging:\n  level: INFO\n  json: false\n",
        )
        config = AppConfig.load(path)
        assert config.logging.json_output is False


class TestUserValidation:
    def test_missing_users_list_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("telegram:\n  bot_token: 't'\n")
        with pytest.raises(ValidationError):
            AppConfig.load(path)

    def test_empty_users_list_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.yaml"
        path.write_text("telegram:\n  bot_token: 't'\nusers: []\n")
        with pytest.raises(ValidationError):
            AppConfig.load(path)


class TestPricing:
    def test_pricing_entries_are_parsed(self, tmp_path: Path) -> None:
        path = _write_yaml(
            tmp_path,
            MINIMAL_YAML
            + """
cost:
  pricing:
    claude-sonnet-4-6:
      input_usd_per_mtok: 3.0
      output_usd_per_mtok: 15.0
    claude-opus-4-6:
      input_usd_per_mtok: 15.0
      output_usd_per_mtok: 75.0
""",
        )
        config = AppConfig.load(path)
        assert "claude-sonnet-4-6" in config.cost.pricing
        assert config.cost.pricing["claude-sonnet-4-6"].input_usd_per_mtok == 3.0
        assert config.cost.pricing["claude-opus-4-6"].output_usd_per_mtok == 75.0
