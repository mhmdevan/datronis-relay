"""`datronis-relay doctor` — validates an existing installation.

Loads config.yaml, checks that at least one adapter is enabled, verifies
the SQLite path is reachable, and pings api.telegram.org if a token is
set. Prints each check with a pass/fail marker and returns a non-zero
exit code if any check failed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from datronis_relay.cli.prompts import CliPrompter, Prompter
from datronis_relay.infrastructure.config import AppConfig


@dataclass
class DoctorOptions:
    config_path: Path = Path("./config.yaml")


def run_doctor(
    options: DoctorOptions,
    prompter: Prompter | None = None,
) -> int:
    active_prompter: Prompter = prompter if prompter is not None else CliPrompter()

    active_prompter.say("")
    active_prompter.say("datronis-relay doctor")
    active_prompter.say("=" * 60)
    active_prompter.say("")

    failures = 0

    # 1. Config file exists
    if not options.config_path.exists():
        active_prompter.say(f"  [FAIL] Config not found: {options.config_path}")
        active_prompter.say("         Run: datronis-relay setup")
        return 1
    active_prompter.say(f"  [OK]   Config file: {options.config_path}")

    # 2. Config parses
    try:
        config = AppConfig.load(options.config_path)
    except Exception as exc:  # pragma: no cover - error path
        active_prompter.say(f"  [FAIL] Config failed to load: {exc}")
        return 1
    active_prompter.say("  [OK]   Config parses against schema")

    # 3. At least one adapter enabled
    telegram_ready = config.telegram.enabled and config.telegram.bot_token.get_secret_value()
    slack_ready = (
        config.slack.enabled
        and config.slack.bot_token.get_secret_value()
        and config.slack.app_token.get_secret_value()
    )
    if telegram_ready:
        active_prompter.say("  [OK]   Telegram adapter: enabled with token")
    else:
        active_prompter.say("  [WARN] Telegram adapter: disabled or missing token")
    if slack_ready:
        active_prompter.say("  [OK]   Slack adapter: enabled with both tokens")
    elif config.slack.enabled:
        active_prompter.say("  [FAIL] Slack adapter: enabled but missing bot/app token")
        failures += 1
    if not telegram_ready and not slack_ready:
        active_prompter.say("  [FAIL] No adapter is ready — set tokens in .env")
        failures += 1

    # 4. SQLite path parent is writable
    sqlite_path = Path(config.storage.sqlite_path)
    parent = sqlite_path.parent or Path(".")
    if parent.exists() and os.access(parent, os.W_OK):
        active_prompter.say(f"  [OK]   SQLite parent dir writable: {parent}")
    elif parent.exists():
        active_prompter.say(f"  [FAIL] SQLite parent dir not writable: {parent}")
        failures += 1
    else:
        active_prompter.say(f"  [WARN] SQLite parent dir does not exist yet: {parent}")

    # 5. At least one user in the allowlist
    if len(config.users) >= 1:
        active_prompter.say(f"  [OK]   Users in allowlist: {len(config.users)}")
    else:
        active_prompter.say("  [FAIL] No users configured in the allowlist")
        failures += 1

    # 6. Claude pricing for the default model
    if config.claude.model in config.cost.pricing:
        active_prompter.say(f"  [OK]   Cost pricing present for {config.claude.model}")
    else:
        active_prompter.say(
            f"  [WARN] No pricing for {config.claude.model} — /cost will show $0.00"
        )

    # 7. Optional: verify Telegram token over the network
    if telegram_ready:
        token = config.telegram.bot_token.get_secret_value()
        _check_telegram_token(active_prompter, token)

    active_prompter.say("")
    if failures == 0:
        active_prompter.say("All checks passed. Run `datronis-relay` to start the bot.")
        return 0
    active_prompter.say(f"{failures} check(s) failed. Fix and re-run `datronis-relay doctor`.")
    return 1


def _check_telegram_token(prompter: Prompter, token: str) -> None:
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read())
        if data.get("ok"):
            username = data.get("result", {}).get("username", "unknown")
            prompter.say(f"  [OK]   Telegram API reachable — bot: @{username}")
        else:
            prompter.say(f"  [FAIL] Telegram API returned not-ok: {data!r}")
    except urllib.error.HTTPError as exc:
        prompter.say(f"  [FAIL] Telegram API HTTP {exc.code} — your token may be invalid")
    except urllib.error.URLError as exc:
        prompter.say(f"  [WARN] Could not reach Telegram API ({exc.reason})")
    except (OSError, json.JSONDecodeError) as exc:
        prompter.say(f"  [WARN] Telegram validation skipped ({exc})")
