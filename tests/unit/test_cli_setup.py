"""Tests for the `datronis-relay setup` wizard and `datronis-relay doctor`."""

from __future__ import annotations

import builtins
import os
import shutil
import stat
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from datronis_relay.cli import setup as cli_setup_mod
from datronis_relay.cli.doctor import DoctorOptions, run_doctor
from datronis_relay.cli.prompts import ScriptedPrompter
from datronis_relay.cli.setup import (
    CollectedConfig,
    SetupOptions,
    _build_users,
    _ensure_claude_cli_available,
    _find_datronis_binary,
    _install_claude_cli_via_npm,
    _is_claude_already_logged_in,
    _maybe_install_systemd_service,
    _maybe_run_claude_login,
    _show_login_url,
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

    def test_storage_paths_use_defaults(self, tmp_path: Path) -> None:
        collected = CollectedConfig(telegram_user_id="1")
        path = tmp_path / "config.yaml"
        _write_config(path, collected)
        data = yaml.safe_load(path.read_text())
        assert data["storage"]["sqlite_path"] == "./data/relay.db"
        assert data["attachments"]["temp_dir"] == "./data/attachments"


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
            skip_external_commands=True,
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
            skip_external_commands=True,
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
            skip_external_commands=True,
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
            skip_external_commands=True,
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
            skip_external_commands=True,
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
            skip_external_commands=True,
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


# ---------------------------------------------------------- dependency checks


class TestEnsureClaudeCliAvailable:
    def test_claude_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            shutil, "which", lambda cmd: "/usr/bin/claude" if cmd == "claude" else None
        )
        prompter = ScriptedPrompter([])
        _ensure_claude_cli_available(prompter)
        assert any("found" in line.lower() for line in prompter.output)

    def test_claude_missing_npm_found_user_declines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _which(cmd: str) -> str | None:
            if cmd == "npm":
                return "/usr/bin/npm"
            return None

        monkeypatch.setattr(shutil, "which", _which)
        prompter = ScriptedPrompter([False])  # decline install
        _ensure_claude_cli_available(prompter)
        assert any("not installed" in line for line in prompter.output)

    def test_claude_missing_npm_found_user_accepts_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _which(cmd: str) -> str | None:
            if cmd == "npm":
                return "/usr/bin/npm"
            return None

        monkeypatch.setattr(shutil, "which", _which)
        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=0))
        prompter = ScriptedPrompter([True])  # accept install
        _ensure_claude_cli_available(prompter)
        assert any("installed successfully" in line for line in prompter.output)

    def test_claude_missing_npm_found_user_accepts_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _which(cmd: str) -> str | None:
            if cmd == "npm":
                return "/usr/bin/npm"
            return None

        monkeypatch.setattr(shutil, "which", _which)
        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=1))
        prompter = ScriptedPrompter([True])  # accept install
        _ensure_claude_cli_available(prompter)
        assert any("failed" in line.lower() for line in prompter.output)

    def test_nothing_installed_shows_instructions(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: None)
        prompter = ScriptedPrompter([])
        _ensure_claude_cli_available(prompter)
        assert any("npm install" in line for line in prompter.output)


class TestInstallClaudeCliViaNpm:
    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=0))
        prompter = ScriptedPrompter([])
        assert _install_claude_cli_via_npm(prompter) is True

    def test_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=1))
        prompter = ScriptedPrompter([])
        assert _install_claude_cli_via_npm(prompter) is False

    def test_npm_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*_a: object, **_k: object) -> object:
            raise FileNotFoundError("npm")

        monkeypatch.setattr(subprocess, "run", _boom)
        prompter = ScriptedPrompter([])
        assert _install_claude_cli_via_npm(prompter) is False

    def test_os_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*_a: object, **_k: object) -> object:
            raise OSError("permission denied")

        monkeypatch.setattr(subprocess, "run", _boom)
        prompter = ScriptedPrompter([])
        assert _install_claude_cli_via_npm(prompter) is False


class TestIsClaudeAlreadyLoggedIn:
    def test_returns_true_when_dot_claude_has_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "credentials.json").write_text("{}")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _is_claude_already_logged_in() is True

    def test_returns_true_for_xdg_config_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / ".config" / "claude"
        config_dir.mkdir(parents=True)
        (config_dir / "auth.json").write_text("{}")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _is_claude_already_logged_in() is True

    def test_returns_false_when_no_dirs_exist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _is_claude_already_logged_in() is False

    def test_returns_false_when_dir_exists_but_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / ".claude").mkdir()
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        assert _is_claude_already_logged_in() is False


class TestMaybeRunClaudeLogin:
    def test_claude_not_on_path_skips(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: None)
        collected = CollectedConfig()
        prompter = ScriptedPrompter([])
        _maybe_run_claude_login(prompter, collected)
        assert not collected.claude_login_done

    def test_already_logged_in_skips_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "creds").write_text("{}")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        collected = CollectedConfig()
        prompter = ScriptedPrompter([])  # no prompts needed
        _maybe_run_claude_login(prompter, collected)
        assert collected.claude_login_done
        assert any("existing" in line.lower() for line in prompter.output)

    def test_user_declines_login(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)  # empty home → not logged in
        collected = CollectedConfig()
        prompter = ScriptedPrompter([False])  # decline
        _maybe_run_claude_login(prompter, collected)
        assert not collected.claude_login_done
        assert any("Skipping" in line for line in prompter.output)

    def test_login_success_with_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            cli_setup_mod,
            "_run_claude_login_with_url_capture",
            lambda: (True, "https://claude.ai/login/device?code=ABCD"),
        )
        collected = CollectedConfig()
        prompter = ScriptedPrompter([True])  # accept
        _maybe_run_claude_login(prompter, collected)
        assert collected.claude_login_done

    def test_login_success_without_url(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            cli_setup_mod,
            "_run_claude_login_with_url_capture",
            lambda: (True, ""),
        )
        collected = CollectedConfig()
        prompter = ScriptedPrompter([True])
        _maybe_run_claude_login(prompter, collected)
        assert collected.claude_login_done

    def test_login_failure_then_decline_retry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        monkeypatch.setattr(
            cli_setup_mod, "_run_claude_login_with_url_capture", lambda: (False, "")
        )
        collected = CollectedConfig()
        prompter = ScriptedPrompter([True, False])  # accept → fails → decline retry
        _maybe_run_claude_login(prompter, collected)
        assert not collected.claude_login_done

    def test_login_failure_then_retry_then_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        call_count = {"n": 0}

        def _alternating() -> tuple[bool, str]:
            call_count["n"] += 1
            return (False, "") if call_count["n"] == 1 else (True, "")

        monkeypatch.setattr(cli_setup_mod, "_run_claude_login_with_url_capture", _alternating)
        collected = CollectedConfig()
        prompter = ScriptedPrompter([True, True])  # accept → fails → retry → succeeds
        _maybe_run_claude_login(prompter, collected)
        assert collected.claude_login_done

    def test_login_file_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        def _boom() -> tuple[bool, str]:
            raise FileNotFoundError("claude")

        monkeypatch.setattr(cli_setup_mod, "_run_claude_login_with_url_capture", _boom)
        collected = CollectedConfig()
        prompter = ScriptedPrompter([True])
        _maybe_run_claude_login(prompter, collected)
        assert not collected.claude_login_done

    def test_login_os_error_then_decline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/claude")
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        def _boom() -> tuple[bool, str]:
            raise OSError("broken pipe")

        monkeypatch.setattr(cli_setup_mod, "_run_claude_login_with_url_capture", _boom)
        collected = CollectedConfig()
        prompter = ScriptedPrompter([True, False])  # accept → error → decline
        _maybe_run_claude_login(prompter, collected)
        assert not collected.claude_login_done


class TestShowLoginUrl:
    def test_displays_url_and_qr(self) -> None:
        prompter = ScriptedPrompter([])
        _show_login_url(prompter, "https://claude.ai/login/test")
        combined = "\n".join(prompter.output)
        assert "https://claude.ai/login/test" in combined
        assert "Copy this URL" in combined

    def test_handles_missing_qrcode_library(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_import = builtins.__import__

        def _block_qrcode(name: str, *args: object, **kwargs: object) -> object:
            if name == "qrcode":
                raise ImportError("no qrcode")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_qrcode)
        prompter = ScriptedPrompter([])
        _show_login_url(prompter, "https://example.com")
        # URL is still displayed even without qrcode library
        assert any("https://example.com" in line for line in prompter.output)


class TestFindDatronsBinary:
    def test_finds_via_shutil_which(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: "/opt/app/.venv/bin/datronis-relay")
        # Make the path "exist" by patching Path.is_file
        monkeypatch.setattr(Path, "is_file", lambda self: "datronis-relay" in str(self))
        result = _find_datronis_binary()
        assert result is not None
        assert "datronis-relay" in result

    def test_finds_sibling_of_sys_executable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: None)
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        binary = venv_bin / "datronis-relay"
        binary.write_text("#!/usr/bin/env python3\n")
        monkeypatch.setattr(sys, "executable", str(venv_bin / "python3.12"))
        result = _find_datronis_binary()
        assert result is not None
        assert result.endswith("datronis-relay")

    def test_finds_in_cwd_venv(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: None)
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")  # no sibling
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        binary = venv_bin / "datronis-relay"
        binary.write_text("#!/usr/bin/env python3\n")
        monkeypatch.chdir(tmp_path)
        result = _find_datronis_binary()
        assert result is not None
        assert result.endswith("datronis-relay")

    def test_returns_none_when_not_found(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(shutil, "which", lambda _: None)
        monkeypatch.setattr(sys, "executable", "/usr/bin/python3")
        monkeypatch.chdir(tmp_path)  # no .venv here
        result = _find_datronis_binary()
        assert result is None


class TestMaybeInstallSystemdService:
    def test_skips_on_non_linux(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        options = SetupOptions(config_path=tmp_path / "c.yaml", env_path=tmp_path / ".env")
        prompter = ScriptedPrompter([])
        assert _maybe_install_systemd_service(prompter, options) is False

    def test_skips_without_systemctl(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(
            shutil, "which", lambda cmd: None if cmd == "systemctl" else "/usr/bin/" + cmd
        )
        options = SetupOptions(config_path=tmp_path / "c.yaml", env_path=tmp_path / ".env")
        prompter = ScriptedPrompter([])
        assert _maybe_install_systemd_service(prompter, options) is False

    def test_user_declines(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/systemctl")
        options = SetupOptions(config_path=tmp_path / "c.yaml", env_path=tmp_path / ".env")
        prompter = ScriptedPrompter([False])  # decline install
        assert _maybe_install_systemd_service(prompter, options) is False

    @pytest.fixture(autouse=True)
    def _patch_binary_finder(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """All systemd tests need _find_datronis_binary to return a path."""
        monkeypatch.setattr(
            cli_setup_mod,
            "_find_datronis_binary",
            lambda: "/opt/app/.venv/bin/datronis-relay",
        )

    def test_user_accepts_and_commands_succeed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(os, "geteuid", lambda: 0)  # pretend root
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(returncode=0, stderr=""),
        )

        config = tmp_path / "c.yaml"
        config.write_text("{}")
        options = SetupOptions(config_path=config, env_path=tmp_path / ".env")
        prompter = ScriptedPrompter([True])  # accept
        assert _maybe_install_systemd_service(prompter, options) is True
        assert any("installed and started" in line for line in prompter.output)

    def test_tee_failure_returns_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(os, "geteuid", lambda: 0)
        monkeypatch.setattr(
            subprocess,
            "run",
            lambda *_a, **_k: SimpleNamespace(returncode=1, stderr="permission denied"),
        )
        config = tmp_path / "c.yaml"
        config.write_text("{}")
        options = SetupOptions(config_path=config, env_path=tmp_path / ".env")
        prompter = ScriptedPrompter([True])
        assert _maybe_install_systemd_service(prompter, options) is False

    def test_sudo_used_when_not_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/systemctl")
        monkeypatch.setattr(os, "geteuid", lambda: 1000)  # not root

        captured_cmds: list[list[str]] = []

        def _capture_run(cmd: list[str], **_kwargs: object) -> SimpleNamespace:
            captured_cmds.append(cmd)
            return SimpleNamespace(returncode=0, stderr="")

        monkeypatch.setattr(subprocess, "run", _capture_run)
        config = tmp_path / "c.yaml"
        config.write_text("{}")
        options = SetupOptions(config_path=config, env_path=tmp_path / ".env")
        prompter = ScriptedPrompter([True])
        _maybe_install_systemd_service(prompter, options)
        # All commands should have been prefixed with 'sudo'
        for cmd in captured_cmds:
            assert cmd[0] == "sudo"


class TestDoctor:
    def _write_valid_config(self, tmp_path: Path) -> Path:
        """Helper: run the wizard to produce a known-good config."""
        prompter = ScriptedPrompter(_happy_path_script())
        options = SetupOptions(
            config_path=tmp_path / "config.yaml",
            env_path=tmp_path / ".env",
            force=True,
            skip_validation=True,
            skip_external_commands=True,
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
