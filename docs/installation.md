# Installation & running

Two paths are documented here:

1. **The 5-minute wizard** — best for getting a real bot running on a
   real server.
2. **The manual path** — best for contributors and power users who want
   to control every step.

For an even more detailed walkthrough, see [`quickstart.md`](./quickstart.md).

## Prerequisites

- **Python 3.11+**
- **Claude Code CLI (native installer)** — `curl -fsSL https://claude.ai/install.sh | bash`. The `claude-agent-sdk` spawns it as a subprocess. The npm package is deprecated — use the native installer. *(The Docker image and `datronis-relay setup` both install this automatically.)*
- **Claude authentication** — **the primary path is subscription login**, not an API key:
    - 🟢 **Recommended (default):** an active **Claude subscription** (Pro / Max / Teams / Enterprise) plus a one-time `claude login`. OAuth credentials persist in `~/.claude`. **No per-token billing, no key rotation, no console quotas to track.** If you already pay for Claude, you're already paying for this bot.
    - 🟡 **Fallback only:** an `ANTHROPIC_API_KEY` from [console.anthropic.com](https://console.anthropic.com). Use this **only** if you don't already have a Claude subscription, or if you specifically want pay-per-token billing for this workload.
- A **Telegram bot token** (from [@BotFather](https://t.me/BotFather)) — **and/or** a Slack app (see [Slack setup](./slack_setup.md))
- **Optional — for the web dashboard:** Node.js 20+ and `pnpm` 10+ (`corepack enable && corepack prepare pnpm@latest --activate`)

---

## Path A — the 5-minute wizard

If you just want the bot running on a server, the interactive wizard
handles everything end-to-end: installs the Claude Code native binary,
runs `claude login` (with a terminal-side QR code so the OAuth URL is
easy to copy on headless hosts), prompts for your Telegram/Slack tokens,
writes `config.yaml`, and installs a hardened `systemd` unit so the bot
starts on boot.

```bash
git clone https://github.com/mhmdevan/datronis-relay.git
cd datronis-relay
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
datronis-relay setup
```

That's it. Skip to **Try it** at the bottom of this page.

---

## Path B — the manual path

### 1. Clone and install

```bash
git clone https://github.com/mhmdevan/datronis-relay.git
cd datronis-relay

python3.11 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Configure

```bash
cp config.example.yaml config.yaml
cp .env.example .env
```

Authenticate with Claude **once** — this is the step that makes the
bot free to run if you already subscribe:

```bash
# 🟢 RECOMMENDED — use your Claude Pro / Max / Teams / Enterprise subscription
claude login
# → follow the browser or device-code prompt.
# → OAuth credentials persist in ~/.claude — no API key to rotate, no console bill to watch.
# → The `datronis-relay setup` wizard runs this for you and shows a QR code
#    of the OAuth URL so you can scan it from a phone on a headless server.

# 🟡 FALLBACK — pay-per-token API key (only if you don't have a Claude subscription)
# Put ANTHROPIC_API_KEY=sk-ant-... into .env and skip `claude login`.
```

Edit `.env` with your secrets:

```env
DATRONIS_TELEGRAM_BOT_TOKEN=123456:ABC-your-bot-token
# ANTHROPIC_API_KEY=sk-ant-...   # optional; leave blank if you ran `claude login`
# Optional Slack:
# DATRONIS_SLACK_BOT_TOKEN=xoxb-...
# DATRONIS_SLACK_APP_TOKEN=xapp-...
```

Edit `config.yaml` to add your numeric Telegram user id to the `users[]`
allowlist (format: `telegram:<numeric_id>`). See
[`quickstart.md`](./quickstart.md) for the full walkthrough.

### 3. Run

```bash
# Local development
datronis-relay

# Docker (multi-stage build, non-root user)
docker compose up --build

# systemd (production, hardened unit)
sudo install -m 644 examples/systemd/datronis-relay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now datronis-relay
journalctl -u datronis-relay -f
```

### 3b. Run the web dashboard (optional)

```bash
cd ui
pnpm install
pnpm dev                    # http://localhost:3210
# Rewrites /api/* to the bot's future REST endpoint on :3100 (Phase UI-5)
```

The dev server runs on **port 3210** (not the conventional 3000) to
avoid clashing with whatever else you might have running locally.

Until the Python REST API ships in Phase UI-5, every page still renders
its full loading / error / empty / success states — the network calls
simply land in the error branch with a retry button. You can preview
the entire UI offline.

### 4. Verify

```bash
# Unit tests (fast)
pytest -m "not integration"

# Integration tests (real SQLite)
pytest -m integration

# Full run + coverage
pytest --cov=datronis_relay

# Type checking
mypy src

# Lint + format
ruff check .
ruff format --check .

# Benchmarks (markdown-emitting)
python scripts/benchmark.py

# Build the documentation site locally
pip install -e ".[docs]"
mkdocs serve   # open http://localhost:8000

# Web dashboard quality gates
cd ui
pnpm typecheck   # tsc --noEmit — zero errors
pnpm lint        # eslint flat config — zero warnings
pnpm test        # vitest run — 108 tests
pnpm build       # production bundle — every route < 250 KB first-load
```

### 5. Try it

On Telegram, open a chat with your bot and send:

- `/start` → welcome
- `/help` → full command list
- `explain SQLite WAL mode` → default `/ask`
- `/schedule 1h check disk usage on prod-web-1` → background worker fires every hour
- `/cost` → your token usage and USD spend

---

## Commands reference

### Chat commands (Telegram / Slack)

| Command | Purpose | Notes |
|---|---|---|
| `/start` | Welcome + onboarding | |
| `/help` | List all commands | |
| `/ask <prompt>` | Send a prompt to Claude | Default when you omit the command |
| `/status` | Show current session id | Persistent across restarts (SQLite) |
| `/stop` | Reset the current session | Closes the active session in SQLite |
| `/cost` | Token usage + USD spend | Today / 7d / 30d / total |
| `/schedule <interval> <prompt>` | Schedule a recurring prompt | Interval: `30s`, `5m`, `2h`, `1d` (min 30s, max 90d) |
| `/schedules` | List your scheduled tasks | |
| `/unschedule <task_id>` | Delete a scheduled task | Users can only delete their own tasks |
| *(send a file or image)* | Claude reads it via its `Read` tool | 10 MB cap by default |

### CLI subcommands

| Command | Purpose | Notes |
|---|---|---|
| `datronis-relay` | Run the bot | Default action; honours `config.yaml` + env vars |
| `datronis-relay setup` | Interactive first-run wizard | Installs Claude Code, prompts for tokens, writes config, installs systemd unit. Pass `--force` to re-run over an existing config. |
| `datronis-relay doctor` | Validate config + connectivity | Reads `config.yaml`, checks that Claude Code is installed + logged in, reports issues without starting the bot |
