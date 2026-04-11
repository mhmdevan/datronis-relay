# datronis-relay — Quickstart (v0.4.0)

Phase 4 ecosystem: Phase 3 multi-platform + **file/image attachments** (Telegram and Slack), **scheduled tasks** (`/schedule`, `/schedules`, `/unschedule`), background worker reusing the same `MessagePipeline` that handles realtime messages.

> Phase 4 is additive on top of Phase 3 — no breaking changes. Existing `config.yaml` files from Phase 3 keep working; new `scheduler` and `attachments` sections have sensible defaults. See [`changelog.md`](./changelog.md) for the full migration walkthrough.

---

## 1. Prerequisites

- **Python 3.11+**
- An **`ANTHROPIC_API_KEY`** for Claude
- A **Telegram bot token** from [@BotFather](https://t.me/BotFather)
- The **namespaced Telegram user id** for every user you want to allow — format is `telegram:<numeric_id>` (send `/start` to [@userinfobot](https://t.me/userinfobot) to get the numeric id)

---

## 2. Install (dev)

```bash
git clone https://github.com/datronis/datronis-relay.git
cd datronis-relay

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

---

## 3. Configure

Copy the example YAML config and fill it in:

```bash
cp config.example.yaml config.yaml
```

Then edit `config.yaml`. The minimum to run:

```yaml
telegram:
  bot_token: "REPLACE_ME"   # or leave blank and use the env var below

claude:
  model: "claude-sonnet-4-6"

storage:
  sqlite_path: "./data/relay.db"

users:
  - id: "telegram:123456789"
    display_name: "Owner"
    allowed_tools: ["Read", "Write", "Bash"]
    rate_limit:
      per_minute: 20
      per_day: 1000
```

Secrets are best kept out of `config.yaml`. Use env vars instead:

```bash
cp .env.example .env
# then edit .env:
#   DATRONIS_TELEGRAM_BOT_TOKEN=...
#   ANTHROPIC_API_KEY=...
```

Env vars always override the YAML value.

---

## 4. Run

### Local

```bash
datronis-relay
```

Optional: `DATRONIS_CONFIG_PATH=/path/to/other/config.yaml datronis-relay`.

### Docker

```bash
docker compose up --build
```

`docker-compose.yml` mounts `./config.yaml` read-only and persists the SQLite database on a named volume (`relay_data`).

### systemd

The Phase 1 unit file in `examples/systemd/datronis-relay.service` still works; in addition, create `/etc/datronis-relay/config.yaml` and point at it with an environment entry in the unit:

```ini
Environment=DATRONIS_CONFIG_PATH=/etc/datronis-relay/config.yaml
```

---

## 5. Commands

| Send                                    | What happens                                           |
|-----------------------------------------|--------------------------------------------------------|
| `/start`                                | welcome message                                        |
| `/help`                                 | list of commands                                       |
| `/status`                               | current session id (persistent across restarts)        |
| `/ask <prompt>` or just `<prompt>`      | routes through rate limiter → Claude, with tool allowlist from YAML |
| `/stop`                                 | resets the session (closes the current one in SQLite)  |
| `/cost`                                 | your token usage and USD spend (today / 7d / 30d / total) |
| `/schedule <interval> <prompt>`         | schedule a recurring prompt — e.g. `/schedule 1h run tests` |
| `/schedules`                            | list your scheduled tasks                              |
| `/unschedule <task_id>`                 | delete a scheduled task                                |
| *send a file or image*                  | downloaded, cleaned up after processing, Claude reads via its Read tool |

While Claude is thinking, the bot sends a typing indicator every 4 seconds. Long replies (>4000 chars) are chunked with `▼ continued` markers.

---

## 6. Test

```bash
# everything
pytest

# unit only
pytest -m "not integration"

# integration only (includes real SQLite + 100-concurrent load sim)
pytest -m integration

# type-check
mypy src

# lint / format
ruff check .
ruff format .
```

Coverage target: **≥ 80%** (enforced via `coverage.report.fail_under` in `pyproject.toml`).

---

## 7. Observability

### Logs
Structured JSON by default. Every inbound message is bound to a `correlation_id` (12-char hex) that propagates through every log line for that request.

### Prometheus
Opt-in. In `config.yaml`:

```yaml
metrics:
  enabled: true
  host: "127.0.0.1"
  port: 9464
```

Exposed metrics (scrape `/metrics` on that port):
- `datronis_messages_total{outcome=...}`
- `datronis_claude_tokens_total{direction=in|out}`
- `datronis_claude_cost_usd_total`
- `datronis_dispatch_duration_seconds` (histogram)

### SQLite inspection
```bash
sqlite3 data/relay.db
.tables
SELECT * FROM audit_log ORDER BY ts DESC LIMIT 20;
SELECT * FROM cost_ledger ORDER BY day DESC, user_id;
```

---

## 8. What's in this release

```
src/datronis_relay/
├── domain/
│   ├── ids.py              # UserId, SessionId, CorrelationId
│   ├── messages.py         # PlatformMessage, ClaudeRequest(+allowed_tools)
│   ├── stream_events.py    # TextChunk | CompletionEvent (Phase 2)
│   ├── user.py             # User with permissions + quotas (Phase 2)
│   ├── audit.py            # AuditEntry + AuditEventType (Phase 2)
│   ├── cost.py             # CostSummary (Phase 2)
│   ├── pricing.py          # ModelPricing (Phase 2)
│   └── errors.py
├── core/
│   ├── ports.py            # + AuditStoreProtocol, CostStoreProtocol
│   ├── auth.py             # authenticate(message) -> User
│   ├── session_manager.py  # unchanged, store now SQLite
│   ├── command_router.py   # + /cost, User, rate limiter, cost tracker
│   ├── rate_limiter.py     # token bucket (Phase 2)
│   ├── cost_tracker.py     # pricing → USD → ledger (Phase 2)
│   └── chunking.py
├── infrastructure/
│   ├── config.py           # YAML-backed AppConfig (Phase 2)
│   ├── sqlite_storage.py   # aiosqlite, WAL, migrations (Phase 2)
│   ├── session_store.py    # InMemorySessionStore — still used in tests
│   ├── claude_client.py    # yields StreamEvent, forwards allowed_tools
│   ├── logging.py
│   ├── metrics.py          # Prometheus (Phase 2)
│   └── migrations/
│       └── 0001_init.sql   # users, sessions, audit_log, cost_ledger
├── adapters/telegram/bot.py  # authenticate → dispatch(message, user)
├── main.py                   # composition root — storage open/close
└── __main__.py
```

---

## 9. Troubleshooting

| Symptom                                          | Likely cause                                           | Fix                                                  |
|--------------------------------------------------|--------------------------------------------------------|------------------------------------------------------|
| `FileNotFoundError: config file not found`      | No `config.yaml` in the working dir                    | Copy `config.example.yaml`, or set `DATRONIS_CONFIG_PATH` |
| Reply starts with `[AUTH]`                       | Telegram id isn't in the `users` list, OR it's missing the `telegram:` prefix | Check `users[].id` in YAML; the format is `telegram:<numeric_id>` |
| Reply starts with `[RATE_LIMIT]`                 | You hit the minute or day quota                        | Raise `users[].rate_limit` in YAML                   |
| Reply starts with `[CLAUDE_API]`                 | SDK couldn't reach Anthropic, or SDK surface drifted   | Verify `ANTHROPIC_API_KEY`; check `claude_client.py` |
| `/cost` shows `$0.00` after real asks            | Your model isn't in `cost.pricing` in YAML             | Add the pricing entry; zero is emitted with a `cost_tracker.unknown_model` warning |
| SQLite errors at startup                         | Parent dir not writable                                | Check `storage.sqlite_path` permissions              |

---

## 10. Slack

Slack is disabled by default. To enable it, follow [`slack_setup.md`](./slack_setup.md) — it walks you through the Slack app config, scopes, Socket Mode, and user id lookup, then has you add:

```yaml
slack:
  enabled: true
  bot_token: "xoxb-..."
  app_token: "xapp-..."

users:
  - id: "slack:U0XXXXXXX"
    display_name: "Me"
    allowed_tools: ["Read", "Bash"]
    rate_limit:
      per_minute: 20
      per_day: 1000
```

Slack and Telegram can run **simultaneously** — the composition root boots every enabled adapter concurrently, and the same `MessagePipeline` handles both. Users are namespaced per platform (`telegram:…` vs `slack:…`), so the same person chatting the bot on both platforms needs two `users[]` entries.

---

## 11. Attachments and scheduled tasks (Phase 4)

### File uploads
Send any file or image in a chat with the bot — it downloads it, Claude reads it via its `Read` tool, and the temp file is deleted as soon as the reply is sent. The default 10 MB cap is configurable under `attachments.max_bytes_per_file` in `config.yaml`.

**Important:** users with an explicit `allowed_tools` list must include `"Read"` for attachments to be useful — Claude relies on that tool to actually inspect the file. Empty `allowed_tools: []` means "no restriction" and works out of the box.

### Scheduled tasks
Interval-based, not cron. Supported units: `s`, `m`, `h`, `d`. Minimum 30 seconds, maximum 90 days.

```
/schedule 5m check disk usage on prod-web-1
/schedule 1h run the integration tests
/schedule 1d post a summary of the audit log
/schedules          # list
/unschedule 3       # delete task #3
```

Each scheduled task runs through the exact same pipeline as a realtime message, so it's subject to rate limits, cost tracking, and per-user tool permissions. Deleted users' tasks stop firing automatically because auth fails at dispatch time.

Configure in `config.yaml` under `scheduler`:

```yaml
scheduler:
  enabled: true               # set false to disable the worker entirely
  poll_interval_seconds: 30   # how often to check for due tasks
  max_tasks_per_user: 50      # per-user cap on active scheduled tasks
  batch_limit: 10             # tasks fired per tick
```

---

## 12. What's next (Phase 2.5)

- **Voice input** (Whisper) + optional TTS replies
- **Multi-server execution backend** (SSH, Docker exec) with per-server permissions
- **Secrets vault** for server credentials
- See [`../datronis-relay-roadmap.md`](../datronis-relay-roadmap.md) for the full plan.
