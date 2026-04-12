"""Interactive setup wizard — `datronis-relay setup`.

Collects every value `datronis-relay` needs at runtime (Telegram bot
token, user id, Claude auth choice, optional Slack tokens, rate limits,
storage paths) via a `Prompter` dependency, then writes a `config.yaml`
and `.env` pair to disk.

The wizard depends on an injected `Prompter` so unit tests can drive it
with a scripted fake — no stdin/stdout interaction in tests.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from datronis_relay.cli.prompts import CliPrompter, Prompter

# Telegram tokens look like "<numeric_bot_id>:<base64-ish secret>".
_TELEGRAM_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]+$")
# Telegram user ids and chat ids are numeric (can be negative for groups).
_USER_ID_RE = re.compile(r"^-?\d+$")
# Anthropic keys currently start with `sk-ant-` but we only use this as a hint.
_ANTHROPIC_KEY_RE = re.compile(r"^sk-ant-[A-Za-z0-9_-]+$")

DEFAULT_CONFIG_PATH = Path("./config.yaml")
DEFAULT_ENV_PATH = Path("./.env")

# Pricing snapshot included in the generated config. Users should update
# these numbers to whatever Anthropic publishes for their subscription tier.
_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input_usd_per_mtok": 3.0, "output_usd_per_mtok": 15.0},
    "claude-opus-4-6": {"input_usd_per_mtok": 15.0, "output_usd_per_mtok": 75.0},
    "claude-haiku-4-5-20251001": {
        "input_usd_per_mtok": 1.0,
        "output_usd_per_mtok": 5.0,
    },
}


@dataclass
class SetupOptions:
    config_path: Path = DEFAULT_CONFIG_PATH
    env_path: Path = DEFAULT_ENV_PATH
    force: bool = False
    skip_validation: bool = False
    skip_external_commands: bool = False  # set True in tests


@dataclass
class CollectedConfig:
    """Everything the wizard gathers before writing files."""

    telegram_token: str = ""
    telegram_user_id: str = ""
    display_name: str = "Me"
    use_api_key: bool = False
    anthropic_api_key: str = ""
    enable_slack: bool = False
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_user_id: str = ""
    allowed_tools: list[str] = field(default_factory=lambda: ["Read", "Write", "Bash"])
    rate_limit_per_minute: int = 20
    rate_limit_per_day: int = 1000
    sqlite_path: str = "./data/relay.db"
    attachments_path: str = "./data/attachments"
    claude_model: str = "claude-sonnet-4-6"
    claude_login_done: bool = False


# --------------------------------------------------------------------- entrypoint


def run_setup(
    options: SetupOptions,
    prompter: Prompter | None = None,
) -> int:
    """Top-level wizard. Returns 0 on success, non-zero on abort/failure."""
    active_prompter: Prompter = prompter if prompter is not None else CliPrompter()

    _print_header(active_prompter)

    if not options.force and (options.config_path.exists() or options.env_path.exists()):
        active_prompter.say(
            f"Existing config found at {options.config_path} or {options.env_path}."
        )
        if not active_prompter.confirm("Overwrite them?", default=False):
            active_prompter.say("")
            active_prompter.say("Aborted. Re-run with --force to overwrite without asking.")
            return 1

    try:
        collected = _collect_all(active_prompter, options)
    except KeyboardInterrupt:
        active_prompter.say("")
        active_prompter.say("Aborted by user (Ctrl+C).")
        return 130

    _write_config(options.config_path, collected)
    _write_env(options.env_path, collected)

    # If subscription mode, offer to run `claude login` now.
    if not collected.use_api_key and not options.skip_external_commands:
        _maybe_run_claude_login(active_prompter, collected)

    # On Linux with systemctl, offer to install as a background service.
    service_installed = False
    if not options.skip_external_commands:
        service_installed = _maybe_install_systemd_service(active_prompter, options)

    _print_footer(active_prompter, collected, options, service_installed)
    return 0


# ---------------------------------------------------------------------- headers


def _print_header(prompter: Prompter) -> None:
    prompter.say("")
    prompter.say("=" * 60)
    prompter.say("  datronis-relay setup wizard")
    prompter.say("=" * 60)
    prompter.say("")
    prompter.say("This wizard creates config.yaml and .env for you.")
    prompter.say("Press Ctrl+C at any time to abort.")
    prompter.say("")


def _print_footer(
    prompter: Prompter,
    collected: CollectedConfig,
    options: SetupOptions,
    service_installed: bool = False,
) -> None:
    prompter.say("")
    prompter.say("=" * 60)
    prompter.say("  Setup complete")
    prompter.say("=" * 60)
    prompter.say(f"  Config:  {options.config_path}")
    prompter.say(f"  Secrets: {options.env_path}")
    prompter.say("")

    if not collected.use_api_key and not collected.claude_login_done:
        if shutil.which("claude"):
            prompter.say("Next — authenticate with Claude:")
            prompter.say("  claude login")
            prompter.say("")
        else:
            prompter.say("Next — install the Claude Code CLI and log in:")
            prompter.say("  npm install -g @anthropic-ai/claude-code")
            prompter.say("  claude login")
            prompter.say("")

    if service_installed:
        prompter.say("The bot is running as a background service.")
        prompter.say("  View logs:       sudo journalctl -u datronis-relay -f")
        prompter.say("  Restart:         sudo systemctl restart datronis-relay")
        prompter.say("  Stop:            sudo systemctl stop datronis-relay")
    else:
        prompter.say("Start the bot:")
        prompter.say("  datronis-relay")
    prompter.say("")


# -------------------------------------------------------------------- collection


def _collect_all(prompter: Prompter, options: SetupOptions) -> CollectedConfig:
    collected = CollectedConfig()
    _collect_telegram_token(prompter, collected)
    _collect_user(prompter, collected)
    _collect_claude_auth(prompter, collected, skip_checks=options.skip_external_commands)
    _collect_slack(prompter, collected)
    _collect_permissions(prompter, collected)
    _collect_storage(prompter, collected)
    if not options.skip_validation:
        _validate_telegram_online(prompter, collected.telegram_token)
    return collected


def _collect_telegram_token(prompter: Prompter, collected: CollectedConfig) -> None:
    prompter.say("Step 1 of 5 — Telegram bot token")
    prompter.say("  Create a bot via @BotFather on Telegram.")
    prompter.say("  The token looks like:  123456789:ABC-xyz_...")
    prompter.say("")
    while True:
        token = prompter.ask_secret("Bot token").strip()
        if not token:
            prompter.say("  Token cannot be empty.")
            continue
        if not _TELEGRAM_TOKEN_RE.match(token):
            prompter.say("  That does not look like a valid Telegram bot token.")
            if not prompter.confirm("  Use it anyway?", default=False):
                continue
        collected.telegram_token = token
        prompter.say("  Saved.")
        prompter.say("")
        return


def _collect_user(prompter: Prompter, collected: CollectedConfig) -> None:
    prompter.say("Step 2 of 5 — Your Telegram user id")
    prompter.say("  Send /start to @userinfobot — it replies with your numeric id.")
    prompter.say("")
    while True:
        raw = prompter.ask("Your numeric user id").strip()
        if _USER_ID_RE.match(raw):
            collected.telegram_user_id = raw
            break
        prompter.say("  User id should be a number, e.g. 123456789.")

    collected.display_name = prompter.ask("Display name (optional)", default="Me")
    prompter.say(f"  Will be added as telegram:{collected.telegram_user_id}")
    prompter.say("")


def _collect_claude_auth(
    prompter: Prompter,
    collected: CollectedConfig,
    *,
    skip_checks: bool = False,
) -> None:
    prompter.say("Step 3 of 5 — Claude authentication")
    prompter.say("")
    choice = prompter.ask_choice(
        "How do you want to authenticate with Claude?",
        [
            "Subscription (Claude Pro / Max / Teams / Enterprise) — recommended",
            "API key (pay-per-token via console.anthropic.com)",
        ],
        default=0,
    )

    if choice == 0:
        collected.use_api_key = False
        if not skip_checks:
            prompter.say("")
            prompter.say("  Checking for the Claude Code CLI...")
            _ensure_claude_cli_available(prompter)
    else:
        collected.use_api_key = True
        while True:
            key = prompter.ask_secret("Anthropic API key (sk-ant-...)").strip()
            if not key:
                prompter.say("  API key cannot be empty.")
                continue
            if not _ANTHROPIC_KEY_RE.match(key):
                prompter.say("  That does not look like a valid Anthropic API key.")
                if not prompter.confirm("  Use it anyway?", default=False):
                    continue
            collected.anthropic_api_key = key
            prompter.say("  Saved.")
            break
    prompter.say("")


def _collect_slack(prompter: Prompter, collected: CollectedConfig) -> None:
    prompter.say("Step 4 of 5 — Slack adapter (optional)")
    if not prompter.confirm("  Enable Slack too?", default=False):
        prompter.say("  Skipping.")
        prompter.say("")
        return

    collected.enable_slack = True
    prompter.say("  See docs/slack_setup.md for how to create the Slack app.")
    collected.slack_bot_token = prompter.ask_secret("Slack bot token (xoxb-...)").strip()
    collected.slack_app_token = prompter.ask_secret("Slack app token (xapp-...)").strip()
    collected.slack_user_id = prompter.ask("Your Slack user id (U...)").strip()
    prompter.say("  Saved.")
    prompter.say("")


def _collect_permissions(prompter: Prompter, collected: CollectedConfig) -> None:
    prompter.say("Step 5 of 5 — Permissions and rate limits")
    prompter.say("")
    choice = prompter.ask_choice(
        "Which tools should Claude be allowed to use?",
        [
            "Safe — Read only (for file inspection + vision)",
            "Standard — Read + Bash (can run commands)",
            "Full — Read + Write + Bash (can modify files)",
        ],
        default=2,
    )

    if choice == 0:
        collected.allowed_tools = ["Read"]
    elif choice == 1:
        collected.allowed_tools = ["Read", "Bash"]
    else:
        collected.allowed_tools = ["Read", "Write", "Bash"]

    prompter.say("")
    per_minute = prompter.ask("Requests per minute", default="20")
    per_day = prompter.ask("Requests per day", default="1000")
    collected.rate_limit_per_minute = _parse_positive_int(per_minute, fallback=20)
    collected.rate_limit_per_day = _parse_positive_int(per_day, fallback=1000)
    prompter.say("")


def _collect_storage(prompter: Prompter, collected: CollectedConfig) -> None:
    # Storage paths use sensible defaults (./data/relay.db, ./data/attachments).
    # No prompt — most users don't need to change them. Power users who need
    # absolute Docker paths can edit config.yaml after setup.
    _ = prompter  # unused; kept for consistency with other _collect_* signatures
    collected.sqlite_path = "./data/relay.db"
    collected.attachments_path = "./data/attachments"


# ---------------------------------------------------------- systemd service


_SYSTEMD_UNIT_TEMPLATE = """\
[Unit]
Description=datronis-relay — chat bridge for the Claude Agent SDK
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
Group={user}
WorkingDirectory={workdir}
Environment=HOME={home}
Environment=PATH={service_path}
Environment=DATRONIS_CONFIG_PATH={config_path}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5s

NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
ReadWritePaths={workdir} {home}

[Install]
WantedBy=multi-user.target
"""

UNIT_FILE_PATH = Path("/etc/systemd/system/datronis-relay.service")


def _find_datronis_binary() -> str | None:
    """Find the absolute path to the `datronis-relay` console script.

    Tries three strategies in order:
      1. shutil.which — finds it on the current PATH (works when the venv
         is activated, which it always is during `datronis-relay setup`).
      2. Look next to sys.executable (the venv's python) for a sibling
         `datronis-relay` script — handles the case where PATH is weird
         but the venv is active.
      3. Look in the cwd's .venv/bin/ — common convention for local venvs.

    Returns the absolute path string, or None if all strategies fail.
    """
    # Strategy 1: PATH lookup
    found = shutil.which("datronis-relay")
    if found and Path(found).is_file():
        return str(Path(found).resolve())

    # Strategy 2: sibling of the running Python interpreter
    sibling = Path(sys.executable).resolve().parent / "datronis-relay"
    if sibling.is_file():
        return str(sibling)

    # Strategy 3: cwd/.venv/bin/
    local_venv = Path.cwd() / ".venv" / "bin" / "datronis-relay"
    if local_venv.is_file():
        return str(local_venv.resolve())

    return None


def _build_service_path(exec_start: str) -> str:
    """Build a PATH for the systemd unit that includes every directory
    the service needs at runtime:

    1. The venv bin/ (where `datronis-relay` lives)
    2. The Node.js bin/ (where `node` lives — needed by the bundled
       `claude` CLI inside claude-agent-sdk). Covers nvm, nodesource,
       Homebrew, and system-package installs.
    3. Standard system directories as a fallback.

    This is the fix for the "claude: command not found" / "node not found"
    crash that happens when Node.js is installed via nvm (which puts it in
    ~/.nvm/versions/node/vX/bin/, not on systemd's default PATH).
    """
    dirs: list[str] = []

    # 1. The directory containing datronis-relay itself
    dirs.append(str(Path(exec_start).parent))

    # 2. The directory containing the `claude` CLI (native installer puts
    #    it in ~/.claude/bin/ by default; could also be /usr/local/bin/).
    claude_path = shutil.which("claude")
    if claude_path:
        dirs.append(str(Path(claude_path).resolve().parent))

    # 3. Common native-installer locations that might not be on PATH yet
    home = Path.home()
    for candidate_dir in [home / ".claude" / "bin", Path("/usr/local/bin")]:
        if (candidate_dir / "claude").is_file():
            dirs.append(str(candidate_dir))

    # 4. The directory containing `node` — some claude versions still need it.
    node_path = shutil.which("node")
    if node_path:
        dirs.append(str(Path(node_path).resolve().parent))

    # 5. Standard system directories
    dirs.extend(
        [
            "/usr/local/sbin",
            "/usr/local/bin",
            "/usr/sbin",
            "/usr/bin",
            "/sbin",
            "/bin",
        ]
    )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return ":".join(unique)


def _maybe_install_systemd_service(prompter: Prompter, options: SetupOptions) -> bool:
    """On Linux with systemctl, offer to install a background service."""
    if sys.platform != "linux":
        return False
    if not shutil.which("systemctl"):
        return False

    prompter.say("")
    prompter.say("  Linux detected with systemd.")
    if not prompter.confirm(
        "  Install as a background service? (auto-starts on boot)", default=True
    ):
        return False

    # Resolve paths for the unit file.
    workdir = Path.cwd().resolve()
    config_path = options.config_path.resolve()
    exec_start = _find_datronis_binary()
    if not exec_start:
        prompter.say("  Could not find the datronis-relay binary on PATH.")
        prompter.say("  Make sure the virtualenv is activated and try again.")
        return False
    user = os.getenv("USER") or os.getenv("LOGNAME") or "root"
    home = str(Path.home().resolve())
    service_path = _build_service_path(exec_start)

    unit_content = _SYSTEMD_UNIT_TEMPLATE.format(
        user=user,
        workdir=workdir,
        home=home,
        config_path=config_path,
        exec_start=exec_start,
        service_path=service_path,
    )

    # Write unit file + reload + enable + start. Needs root.
    prompter.say(f"  Writing {UNIT_FILE_PATH}")
    cmds = [
        ["tee", str(UNIT_FILE_PATH)],
        ["systemctl", "daemon-reload"],
        ["systemctl", "enable", "--now", "datronis-relay"],
    ]

    use_sudo = os.geteuid() != 0

    try:
        # Write unit file via tee (handles sudo cleanly)
        tee_cmd = ["sudo", "tee", str(UNIT_FILE_PATH)] if use_sudo else ["tee", str(UNIT_FILE_PATH)]
        tee_proc = subprocess.run(
            tee_cmd,
            input=unit_content,
            text=True,
            capture_output=True,
            check=False,
        )
        if tee_proc.returncode != 0:
            prompter.say(f"  Failed to write unit file: {tee_proc.stderr.strip()}")
            return False

        for cmd in cmds[1:]:
            full_cmd = ["sudo", *cmd] if use_sudo else cmd
            prompter.say(f"  Running: {' '.join(full_cmd)}")
            result = subprocess.run(full_cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                prompter.say(f"  Failed: {result.stderr.strip()}")
                return False

        prompter.say("  Service installed and started.")
        return True
    except FileNotFoundError:
        prompter.say("  sudo or systemctl not found on PATH.")
        return False
    except OSError as exc:
        prompter.say(f"  Error installing service: {exc}")
        return False


# ----------------------------------------------------------- dependency checks


def _test_claude_cli_works() -> tuple[bool, str]:
    """Check if `claude` is on PATH AND actually works.

    Returns (works: bool, version_or_error: str). A CLI that exists but
    prints "switched from npm to native installer" is considered broken.
    """
    claude_path = shutil.which("claude")
    if not claude_path:
        return False, "not found on PATH"
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            return False, output or f"exit code {result.returncode}"
        if "native installer" in output.lower() or "switched" in output.lower():
            return False, "npm version is deprecated — needs native install"
        return True, output
    except subprocess.TimeoutExpired:
        return False, "timed out"
    except FileNotFoundError:
        return False, "binary not found"
    except OSError as exc:
        return False, str(exc)


def _ensure_claude_cli_available(prompter: Prompter) -> None:
    """Check if the Claude Code CLI works. If not, install via the native
    installer (curl). The old npm-based install is deprecated by Anthropic.
    """
    works, info = _test_claude_cli_works()
    if works:
        prompter.say(f"  Claude Code CLI: {info}")
        return

    if shutil.which("claude"):
        prompter.say(f"  Claude Code CLI found but not working: {info}")
    else:
        prompter.say("  Claude Code CLI is not installed.")
    prompter.say("")

    if not shutil.which("curl"):
        prompter.say("  `curl` is required to install the Claude Code CLI.")
        prompter.say("  Install curl, then run setup again.")
        return

    if prompter.confirm(
        "  Install Claude Code CLI now?", default=True
    ) and _install_claude_cli_native(prompter):
        return

    prompter.say("")
    prompter.say("  You can install it manually later:")
    prompter.say("    curl -fsSL https://claude.ai/install.sh | sh")
    prompter.say("")
    prompter.say("  Setup will continue without it.")


def _install_claude_cli_native(prompter: Prompter) -> bool:
    """Install Claude Code CLI via Anthropic's native installer.

    Uses `curl -fsSL https://claude.ai/install.sh | sh` — the canonical
    install method since Anthropic deprecated the npm package.
    """
    prompter.say("  Installing Claude Code CLI (native installer)...")
    prompter.say("  Running: curl -fsSL https://claude.ai/install.sh | sh")
    prompter.say("")
    try:
        result = subprocess.run(
            ["sh", "-c", "curl -fsSL https://claude.ai/install.sh | sh"],
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            prompter.say(f"  Installation failed (exit code {result.returncode}).")
            return False

        # The native installer may put the binary in ~/.claude/bin or
        # /usr/local/bin. Rehash PATH to find it.
        works, info = _test_claude_cli_works()
        if works:
            prompter.say(f"  Claude Code CLI installed: {info}")
            return True

        # The installer might have added it to a dir not yet on PATH.
        # Check common locations.
        for candidate in [
            Path.home() / ".claude" / "bin" / "claude",
            Path("/usr/local/bin/claude"),
        ]:
            if candidate.is_file():
                # Add to PATH for this process so later steps find it
                os.environ["PATH"] = str(candidate.parent) + ":" + os.environ.get("PATH", "")
                prompter.say(f"  Installed at {candidate}")
                return True

        prompter.say("  Installer ran but `claude` is still not on PATH.")
        prompter.say("  You may need to restart your shell or add it to PATH.")
        return False
    except subprocess.TimeoutExpired:
        prompter.say("  Installation timed out after 120 seconds.")
        return False
    except FileNotFoundError:
        prompter.say("  `curl` or `sh` not found on PATH.")
        return False
    except OSError as exc:
        prompter.say(f"  Installation error: {exc}")
        return False


def _is_claude_already_logged_in() -> bool:
    """Check if Claude CLI credentials already exist on disk."""
    home = Path.home()
    for candidate in [home / ".claude", home / ".config" / "claude"]:
        if candidate.is_dir() and any(candidate.iterdir()):
            return True
    return False


def _maybe_run_claude_login(prompter: Prompter, collected: CollectedConfig) -> None:
    """Offer to run `claude login` interactively at the end of setup."""
    if not shutil.which("claude"):
        return

    if _is_claude_already_logged_in():
        prompter.say("")
        prompter.say("  Existing Claude credentials found — skipping login.")
        collected.claude_login_done = True
        return

    prompter.say("")
    if not prompter.confirm("Run `claude login` now?", default=True):
        prompter.say("  Skipping. Run `claude login` manually before starting the bot.")
        return

    while True:
        prompter.say("")
        prompter.say("  Running Claude login...")
        prompter.say("")

        try:
            success, url = _run_claude_login_with_url_capture()
            if url:
                _show_login_url(prompter, url)
            if success:
                prompter.say("")
                prompter.say("  Claude login completed successfully.")
                collected.claude_login_done = True
                return
            prompter.say("")
            prompter.say("  Login did not complete.")
        except KeyboardInterrupt:
            prompter.say("")
            prompter.say("  Login interrupted.")
        except FileNotFoundError:
            prompter.say("  `claude` command not found.")
            return
        except OSError as exc:
            prompter.say(f"  Error: {exc}")

        if not prompter.confirm("  Try again?", default=True):
            prompter.say("  Skipping. Run `claude login` manually before starting the bot.")
            return


_URL_PATTERN = re.compile(r"(https?://\S+)")


def _run_claude_login_with_url_capture() -> tuple[bool, str]:
    """Run `claude login`, stream its output to the terminal, and capture
    any URL it prints (for QR code display).

    Returns (success: bool, extracted_url: str). The URL may be empty if
    the CLI didn't print one (e.g. already logged in, or newer CLI version
    with a different flow).
    """
    captured_url = ""
    process = subprocess.Popen(
        ["claude", "login"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert process.stdout is not None
    try:
        for line in process.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            if not captured_url:
                match = _URL_PATTERN.search(line)
                if match:
                    captured_url = match.group(1).rstrip(")")
    except KeyboardInterrupt:
        process.terminate()
        raise
    finally:
        process.wait()
    return process.returncode == 0, captured_url


def _show_login_url(prompter: Prompter, url: str) -> None:
    """Display a login URL in a copy-friendly way + as a terminal QR code.

    The QR code is the killer feature for headless Linux / SSH. The user
    points their phone camera at the terminal and the browser opens
    automatically — no copy-paste of wrapped URLs needed.
    """
    prompter.say("")
    prompter.say("  ┌─────────────────────────────────────────────┐")
    prompter.say("  │  Copy this URL if the browser didn't open:  │")
    prompter.say("  └─────────────────────────────────────────────┘")
    prompter.say("")
    prompter.say(f"  {url}")
    prompter.say("")

    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        prompter.say("  Or scan this QR code with your phone:")
        prompter.say("")
        # qr.print_ascii() prints to stdout directly — we call it and
        # let it render. No way to route through prompter without
        # capturing stdout, which isn't worth the complexity.
        qr.print_ascii(invert=True)
        prompter.say("")
    except ImportError:
        # qrcode not installed — skip gracefully. The URL is still shown.
        pass
    except Exception:
        # Any rendering issue — the URL was already shown, so this is safe.
        pass


def _parse_positive_int(value: str, fallback: int) -> int:
    try:
        parsed = int(value.strip())
    except (ValueError, AttributeError):
        return fallback
    return parsed if parsed > 0 else fallback


# --------------------------------------------------------------------- validation


def _validate_telegram_online(prompter: Prompter, token: str) -> None:
    """Optional network check — best effort, never fatal."""
    prompter.say("Validating Telegram token against api.telegram.org...")
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read()
        data = json.loads(body)
        if data.get("ok"):
            username = data.get("result", {}).get("username", "unknown")
            prompter.say(f"  OK — bot username: @{username}")
        else:
            prompter.say(f"  Warning: Telegram returned not-ok: {data!r}")
    except urllib.error.HTTPError as exc:
        prompter.say(f"  Warning: Telegram returned HTTP {exc.code} — your token may be invalid.")
    except urllib.error.URLError as exc:
        prompter.say(f"  Warning: could not reach Telegram ({exc.reason}).")
        prompter.say("  (The bot will fail at runtime if the token is wrong.)")
    except (OSError, json.JSONDecodeError) as exc:
        prompter.say(f"  Warning: unexpected error during validation ({exc}).")
    prompter.say("")


# --------------------------------------------------------------------- file I/O


def _write_config(path: Path, collected: CollectedConfig) -> None:
    data: dict[str, Any] = {
        "telegram": {
            "enabled": True,
            # Real value lives in .env as DATRONIS_TELEGRAM_BOT_TOKEN.
            "bot_token": "",
        },
        "slack": {
            "enabled": collected.enable_slack,
            "bot_token": "",
            "app_token": "",
        },
        "claude": {
            "model": collected.claude_model,
            "max_turns": 10,
        },
        "storage": {
            "sqlite_path": collected.sqlite_path,
        },
        "attachments": {
            "enabled": True,
            "max_bytes_per_file": 10 * 1024 * 1024,
            "temp_dir": collected.attachments_path,
        },
        "logging": {
            "level": "INFO",
            # YAML key stays `json` (the pydantic alias); Python attribute
            # is `json_output`. See docs/api_reference.md.
            "json": True,
        },
        "scheduler": {
            "enabled": True,
            "poll_interval_seconds": 30,
            "max_tasks_per_user": 50,
            "batch_limit": 10,
        },
        "metrics": {
            "enabled": False,
            "host": "127.0.0.1",
            "port": 9464,
        },
        "users": _build_users(collected),
        "cost": {"pricing": _DEFAULT_PRICING},
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# datronis-relay config — generated by `datronis-relay setup`.\n"
        "# Secrets live in .env (DATRONIS_TELEGRAM_BOT_TOKEN, etc.); the values\n"
        "# here with empty strings are populated from those env vars at runtime.\n"
        "# See config.example.yaml for the full reference with comments.\n"
        "\n"
    )
    body = yaml.safe_dump(data, sort_keys=False, indent=2, allow_unicode=True)
    path.write_text(header + body)


def _build_users(collected: CollectedConfig) -> list[dict[str, Any]]:
    users: list[dict[str, Any]] = [
        {
            "id": f"telegram:{collected.telegram_user_id}",
            "display_name": collected.display_name,
            "allowed_tools": collected.allowed_tools,
            "rate_limit": {
                "per_minute": collected.rate_limit_per_minute,
                "per_day": collected.rate_limit_per_day,
            },
        }
    ]
    if collected.enable_slack and collected.slack_user_id:
        users.append(
            {
                "id": f"slack:{collected.slack_user_id}",
                "display_name": f"{collected.display_name} (Slack)",
                "allowed_tools": collected.allowed_tools,
                "rate_limit": {
                    "per_minute": collected.rate_limit_per_minute,
                    "per_day": collected.rate_limit_per_day,
                },
            }
        )
    return users


def _write_env(path: Path, collected: CollectedConfig) -> None:
    lines: list[str] = [
        "# datronis-relay secrets — DO NOT COMMIT",
        "# Generated by `datronis-relay setup`",
        "",
        f"DATRONIS_TELEGRAM_BOT_TOKEN={collected.telegram_token}",
    ]
    if collected.use_api_key:
        lines.append(f"ANTHROPIC_API_KEY={collected.anthropic_api_key}")
    if collected.enable_slack:
        lines.append(f"DATRONIS_SLACK_BOT_TOKEN={collected.slack_bot_token}")
        lines.append(f"DATRONIS_SLACK_APP_TOKEN={collected.slack_app_token}")
    lines.append("")  # trailing newline

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))

    # Protect the secrets file: owner read/write only. Best-effort — on
    # filesystems that don't support POSIX permissions (Windows mostly)
    # the chmod is silently ignored.
    with contextlib.suppress(PermissionError, OSError):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
