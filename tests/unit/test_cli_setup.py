"""Tests for the `datronis-relay setup` wizard and `datronis-relay doctor`."""

from __future__ import annotations

import os
import stat
import urllib.request
from pathlib import Path

import pytest
import yaml

from datronis_relay.cli.doctor import DoctorOptions, run_doctor
from datronis_relay.cli.prompts import ScriptedPrompter
from datronis_relay.cli.setup import (
    CollectedConfig,
    SetupOptions,
    _build_users,
    _write_config,
    _write_env,
    run_setup,
)
from datronis_relay.infrastructure.config import AppConfig

# ---------------------------------------------------------------------- helpers


def _happy_path_script(*, slack: bool = False, use_api_key: bool = False) -> list[object]:
    """The sequence of answers the happy path wizard expects."""
    script: list[object] = [
        "123456789:ABC-test-token-value",  # ask_secret — bot token
        "42",  # ask — user id
        "Alice",  # ask — display name
        1 if use_api_key else 0,  # ask_choice — auth mode
    ]
    if use_api_key:
        script.append("sk-ant-test-key-1234567890")  # ask_secret — anthropic key
    script.append(slack)  # confirm — enable slack
    if slack:
        script.extend(
            [
                "xoxb-test",  # slack bot token
                "xapp-test",  # slack app token
                "U12345",  # slack user id
            ]
        )
    script.extend(
        [
            2,  # ask_choice — permissions (Full)
            "25",  # ask — per_minute
            "500",  # ask — per_day
            "./tmp/relay.db",  # ask — sqlite path
            "./tmp/attachments",  # ask — attachments path
        ]
    )
    return script


# -------------------------------------------------------------------- _write_env


class TestWriteEnv:
    def test_writes_telegram_token(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_token="123:abc")
        path = tmp_path / ".env"
        _write_env(path, collected)
        assert "DATRONIS_TELEGRAM_BOT_TOKEN=123:abc" in path.read_text()

    def test_writes_api_key_in_api_key_mode(self, tmp_path: Path) -> None:
        collected = CollectedConfig(
            telegram_token="t",
            use_api_key=True,
            anthropic_api_key="sk-ant-xyz",
        )
        path = tmp_path / ".env"
        _write_env(path, collected)
        content = path.read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-xyz" in content

    def test_skips_api_key_in_subscription_mode(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_token="t", use_api_key=False)
        path = tmp_path / ".env"
        _write_env(path, collected)
        assert "ANTHROPIC_API_KEY" not in path.read_text()

    def test_writes_slack_tokens_when_enabled(self, tmp_path: Path) -> None:
        collected = CollectedConfig(
            telegram_token="t",
            enable_slack=True,
            slack_bot_token="xoxb-1",
            slack_app_token="xapp-1",
        )
        path = tmp_path / ".env"
        _write_env(path, collected)
        content = path.read_text()
        assert "DATRONIS_SLACK_BOT_TOKEN=xoxb-1" in content
        assert "DATRONIS_SLACK_APP_TOKEN=xapp-1" in content

    def test_file_mode_is_600_on_posix(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_token="t")
        path = tmp_path / ".env"
        _write_env(path, collected)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600


# -------------------------------------------------------------------- _write_config


class TestWriteConfig:
    def test_header_comment_present(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_user_id="1")
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        first_line = path.read_text().splitlines()[0]
        assert first_line.startswith("# datronis-relay config")

    def test_yaml_parses(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_user_id="1", display_name="Mohammad")
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        data = yaml.safe_load(path.read_text())
        assert data["telegram"]["enabled"] is True
        assert data["users"][0]["id"] == "telegram:1"
        assert data["users"][0]["display_name"] == "Mohammad"

    def test_user_with_all_three_tools(self, tmp_path: Path) -> None:
        collected = CollectedConfig(
            telegram_user_id="42",
            allowed_tools=["Read", "Write", "Bash"],
        )
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        data = yaml.safe_load(path.read_text())
        assert data["users"][0]["allowed_tools"] == ["Read", "Write", "Bash"]

    def test_slack_user_added_when_slack_enabled(self, tmp_path: Path) -> None:
        collected = CollectedConfig(
            telegram_user_id="1",
            enable_slack=True,
            slack_user_id="U9",
        )
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        data = yaml.safe_load(path.read_text())
        ids = [u["id"] for u in data["users"]]
        assert "telegram:1" in ids
        assert "slack:U9" in ids

    def test_pricing_defaults_present(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_user_id="1")
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        data = yaml.safe_load(path.read_text())
        assert "claude-sonnet-4-6" in data["cost"]["pricing"]

    def test_storage_paths_are_persisted(self, tmp_path: Path) -> None:
        collected = CollectedConfig(
            telegram_user_id="1",
            sqlite_path="/var/lib/datronis-relay/relay.db",
            attachments_path="/var/lib/datronis-relay/attachments",
        )
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        data = yaml.safe_load(path.read_text())
        assert data["storage"]["sqlite_path"] == "/var/lib/datronis-relay/relay.db"
        assert data["attachments"]["temp_dir"] == "/var/lib/datronis-relay/attachments"


# -------------------------------------------------------------------- _build_users


class TestBuildUsers:
    def test_telegram_only(self) -> None:
        collected = CollectedConfig(telegram_user_id="42")
        users = _build_users(collected)
        assert len(users) == 1
        assert users[0]["id"] == "telegram:42"

    def test_slack_user_appended(self) -> None:
        collected = CollectedConfig(
            telegram_user_id="42",
            enable_slack=True,
            slack_user_id="U1",
        )
        users = _build_users(collected)
        assert len(users) == 2
        assert users[1]["id"] == "slack:U1"

    def test_slack_without_user_id_is_skipped(self) -> None:
        collected = CollectedConfig(
            telegram_user_id="42",
            enable_slack=True,
            slack_user_id="",
        )
        users = _build_users(collected)
        assert len(users) == 1


# -------------------------------------------------------------------- run_setup


class TestRunSetup:
    def test_happy_path_writes_both_files(self, tmp_path: Path) -> None:
        prompter = ScriptedPrompter(_happy_path_script())
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        result = run_setup(options, prompter=prompter)
        assert result == 0
        assert (tmp_path / "config.yaml").exists()
        assert (tmp_path / ".env").exists()

    def test_api_key_mode_writes_key(self, tmp_path: Path) -> None:
        prompter = ScriptedPrompter(_happy_path_script(use_api_key=True))
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        run_setup(options, prompter=prompter)
        env_content = (tmp_path / ".env").read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-test-key-1234567890" in env_content

    def test_subscription_mode_omits_api_key(self, tmp_path: Path) -> None:
        prompter = ScriptedPrompter(_happy_path_script(use_api_key=False))
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        run_setup(options, prompter=prompter)
        env_content = (tmp_path / ".env").read_text()
        assert "ANTHROPIC_API_KEY" not in env_content

    def test_slack_enabled_writes_both_tokens(self, tmp_path: Path) -> None:
        prompter = ScriptedPrompter(_happy_path_script(slack=True))
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        run_setup(options, prompter=prompter)
        env = (tmp_path / ".env").read_text()
        assert "xoxb-test" in env
        assert "xapp-test" in env

    def test_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("existing")
        prompter = ScriptedPrompter([False])  # confirm "Overwrite them?" → no
        options = SetupOptions(config_path=config, env_path=tmp_path / ".env", force=False)
        result = run_setup(options, prompter=prompter)
        assert result == 1
        assert config.read_text() == "existing"

    def test_overwrites_with_force(self, tmp_path: Path) -> None:
        config = tmp_path / "config.yaml"
        config.write_text("existing content")
        prompter = ScriptedPrompter(_happy_path_script())
        options = SetupOptions(
            config_path=config,
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        result = run_setup(options, prompter=prompter)
        assert result == 0
        assert "existing content" not in config.read_text()

    def test_generated_config_loads_via_appconfig(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The wizard's output must round-trip through `AppConfig.load`."""
        prompter = ScriptedPrompter(_happy_path_script(use_api_key=True))
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        run_setup(options, prompter=prompter)

        # Load via the real pydantic-backed loader. The generated YAML
        # leaves bot_token empty and expects the env var to fill it in.
        monkeypatch.setenv("DATRONIS_TELEGRAM_BOT_TOKEN", "123456:live-token")
        config = AppConfig.load(tmp_path / "config.yaml")
        assert config.telegram.enabled is True
        assert len(config.users) == 1
        assert config.users[0].id == "telegram:42"
        assert config.users[0].display_name == "Alice"


# -------------------------------------------------------------------- doctor


class TestDoctor:
    def _write_valid_config(self, tmp_path: Path) -> Path:
        """Helper: run the wizard to produce a known-good config."""
        prompter = ScriptedPrompter(_happy_path_script())
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
        )
        run_setup(options, prompter=prompter)
        return tmp_path / "config.yaml"

    def test_missing_config_fails(self, tmp_path: Path) -> None:
        prompter = ScriptedPrompter([])
        options = DoctorOptions(config_path=tmp_path / "nonexistent.yaml")
        result = run_doctor(options, prompter=prompter)
        assert result == 1
        assert any("not found" in line for line in prompter.output)

    def test_valid_config_passes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATRONIS_TELEGRAM_BOT_TOKEN", "123456:live")
        config_path = self._write_valid_config(tmp_path)
        prompter = ScriptedPrompter([])
        options = DoctorOptions(config_path=config_path)

        # Stub out urlopen so we don't hit the network
        def _fake_urlopen(*_args: object, **_kwargs: object) -> object:
            raise OSError("offline for test")

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        result = run_doctor(options, prompter=prompter)
        assert result == 0
        assert any("Config file:" in line for line in prompter.output)
        assert any("Users in allowlist" in line for line in prompter.output)

    def test_slack_enabled_without_tokens_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Write a config that enables Slack but leaves tokens blank.
        monkeypatch.setenv("DATRONIS_TELEGRAM_BOT_TOKEN", "123456:live")
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            """
telegram:
  enabled: true
  bot_token: ""
slack:
  enabled: true
  bot_token: ""
  app_token: ""
users:
  - id: "telegram:1"
    display_name: "Me"
    allowed_tools: ["Read"]
    rate_limit:
      per_minute: 20
      per_day: 1000
"""
        )
        prompter = ScriptedPrompter([])
        result = run_doctor(DoctorOptions(config_path=config_path), prompter=prompter)
        assert result == 1
        assert any("Slack adapter: enabled but missing" in line for line in prompter.output)
