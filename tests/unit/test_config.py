"""Tests for `infrastructure/config.py` — YAML loader, env overrides,
pydantic validation, and the `json` field alias."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from datronis_relay.infrastructure.config import _DOTENV_LOADED, AppConfig, _load_dotenv


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


class TestLoadDotenv:
    @pytest.fixture(autouse=True)
    def _clear_loaded_cache(self) -> None:
        _DOTENV_LOADED.clear()

    def test_loads_key_value_pairs(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("FOO_TEST_KEY=bar123\n")
        os.environ.pop("FOO_TEST_KEY", None)
        _load_dotenv(env_file)
        assert os.environ.get("FOO_TEST_KEY") == "bar123"
        os.environ.pop("FOO_TEST_KEY", None)

    def test_ignores_comments_and_blank_lines(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY_A=1\n  # indented comment\nKEY_B=2\n")
        os.environ.pop("KEY_A", None)
        os.environ.pop("KEY_B", None)
        _load_dotenv(env_file)
        assert os.environ.get("KEY_A") == "1"
        assert os.environ.get("KEY_B") == "2"
        os.environ.pop("KEY_A", None)
        os.environ.pop("KEY_B", None)

    def test_strips_quotes(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("QUOTED_KEY=\"hello world\"\nSINGLE='value'\n")
        os.environ.pop("QUOTED_KEY", None)
        os.environ.pop("SINGLE", None)
        _load_dotenv(env_file)
        assert os.environ.get("QUOTED_KEY") == "hello world"
        assert os.environ.get("SINGLE") == "value"
        os.environ.pop("QUOTED_KEY", None)
        os.environ.pop("SINGLE", None)

    def test_real_env_takes_precedence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_KEY=from_file\n")
        monkeypatch.setenv("EXISTING_KEY", "from_shell")
        _load_dotenv(env_file)
        assert os.environ.get("EXISTING_KEY") == "from_shell"

    def test_skips_missing_file(self, tmp_path: Path) -> None:
        _load_dotenv(tmp_path / "nonexistent")  # must not raise

    def test_loads_same_file_only_once(self, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("ONCE_KEY=first\n")
        os.environ.pop("ONCE_KEY", None)
        _load_dotenv(env_file)
        assert os.environ.get("ONCE_KEY") == "first"
        os.environ["ONCE_KEY"] = "overwritten"
        _load_dotenv(env_file)  # should be a no-op (already loaded)
        assert os.environ.get("ONCE_KEY") == "overwritten"
        os.environ.pop("ONCE_KEY", None)

    def test_dotenv_is_loaded_by_appconfig(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """End-to-end: AppConfig.load reads .env next to config.yaml."""
        env_file = tmp_path / ".env"
        env_file.write_text("DATRONIS_TELEGRAM_BOT_TOKEN=from-dotenv\n")
        config_path = _write_yaml(tmp_path, MINIMAL_YAML)
        monkeypatch.delenv("DATRONIS_TELEGRAM_BOT_TOKEN", raising=False)
        config = AppConfig.load(config_path)
        assert config.telegram.bot_token.get_secret_value() == "from-dotenv"


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
