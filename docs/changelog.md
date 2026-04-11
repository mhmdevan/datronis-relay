# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning follows [SemVer](https://semver.org/) **strictly from v1.0.0 onward** — see [`versioning.md`](./versioning.md) for the full contract.

## [Unreleased]

### Fixed (pre-1.0 — will be absorbed into v1.0.0 on tag)
- **Auth model was documented and packaged wrong.** `claude-agent-sdk` inherits authentication from the Claude Code CLI, which supports BOTH an OAuth subscription login (Pro / Max / Teams / Enterprise via `claude login`) and a pay-per-token `ANTHROPIC_API_KEY`. Earlier docs, `.env.example`, `docker-compose.yml`, and the quickstart presented the API key as required — it is not. The subscription path is now the documented default; the API key is the optional alternative.
- **Dockerfile was missing the Claude Code CLI.** `claude-agent-sdk` spawns the `claude` Node.js CLI as a subprocess. The previous image only installed the Python package, so the bot would have failed at runtime with "command not found" on the first `/ask`. The Dockerfile now installs Node.js 20 + `@anthropic-ai/claude-code` globally and declares a `VOLUME` at `/home/relay/.claude` so subscription credentials persist across `docker compose down && up` cycles.
- **`docker-compose.yml`** gains a `claude_credentials` named volume for persistent OAuth tokens, and `ANTHROPIC_API_KEY` is now explicitly optional via `${ANTHROPIC_API_KEY:-}`.
- **`examples/systemd/datronis-relay.service`** now sets `Environment=HOME=/var/lib/datronis-relay/home` so `claude login` can write credentials under `ReadWritePaths` while `ProtectHome=true` continues to block `/home`, `/root`, and `/run/user`. Also adds `EnvironmentFile=-/etc/datronis-relay/datronis-relay.env` (optional) and an explicit `DATRONIS_CONFIG_PATH` entry.
- **`.env.example`** leads with the subscription path and explicitly marks `ANTHROPIC_API_KEY` as optional with a block comment explaining the two auth modes.
- **`config.example.yaml` header** now documents the two auth modes.
- **`docs/quickstart.md`** has a new "Authenticate with Claude (one-time)" section for each deployment path (local venv, Docker, systemd), leading with `claude login` and listing the API key as the alternative.
- **`SECURITY.md`** hardening checklist updated: `ANTHROPIC_API_KEY` rotation is now conditional on "*if you use the API key path*"; subscription-path users revoke via the Claude.ai dashboard.

## [1.0.0] — 2026-04-11

**This is the API freeze.** From this release on, the public surface listed in [`api_reference.md`](./api_reference.md) is guaranteed stable under SemVer. Breaking changes to any public symbol require a v2.0.0 bump and a one-minor-cycle deprecation window.

v1.0.0 is **additive** on top of v0.4.0. No public symbols were removed, renamed, or reshaped. If v0.4.0 worked for you, v1.0.0 works for you — upgrade is `pip install -U datronis-relay` with no other steps.

### Added
- **`docs/api_reference.md`** — the single source of truth for what's public and what's internal. Every symbol your code is allowed to import is listed.
- **`docs/versioning.md`** — the SemVer contract and deprecation policy. One-minor-cycle deprecation window, explicit breaking/non-breaking tables, FAQ.
- **`docs/performance.md`** + **`scripts/benchmark.py`** — reproducible benchmarks for the dispatch path, SQLite hot path, and concurrent throughput. Run with `python scripts/benchmark.py`.
- **`docs/release_checklist.md`** — the release process, pre-flight, tagging, post-release.
- **`docs/index.md`** — landing page for the mkdocs-material site.
- **`mkdocs.yml`** — documentation site configuration. Deploys to GitHub Pages on every push to `main` that touches `docs/` or `mkdocs.yml`.
- **`.github/workflows/ci.yml`** — lint + typecheck + test (Python 3.11 and 3.12) + build on every push and PR.
- **`.github/workflows/release.yml`** — tag-triggered release pipeline. Verifies the tag matches `pyproject.toml` and `__init__.py`, re-runs the full test suite, builds sdist + wheel, publishes to PyPI via trusted publishing, creates a GitHub release with the artifacts.
- **`.github/workflows/docs.yml`** — builds mkdocs-material with `--strict` and deploys to GitHub Pages.
- **`LICENSE`** (MIT), **`CONTRIBUTING.md`**, **`CODE_OF_CONDUCT.md`** (Contributor Covenant v2.1), **`SECURITY.md`** (private reporting process, response SLA, hardening checklist).
- **`.github/ISSUE_TEMPLATE/bug.yml`**, **`feature.yml`**, **`config.yml`**, **`.github/PULL_REQUEST_TEMPLATE.md`** — structured intake for contributions.
- **`[docs]` optional-dependency group** in `pyproject.toml` — `mkdocs-material` is pulled in only when you need to build the site.
- **PyPI classifier** upgraded from `Development Status :: 3 - Alpha` to `5 - Production/Stable`.

### Changed
- **`pyproject.toml` version** → `1.0.0`. The `src/datronis_relay/__init__.py` `__version__` matches.
- **`README.md`** status line updated. Added links to the new reference docs.

### Committed stability guarantees
- Every symbol in [`api_reference.md`](./api_reference.md) is frozen for the 1.x series.
- Adding new optional parameters, fields, and Protocol methods remains non-breaking.
- Removing, renaming, or reshaping anything public requires v2.0.0 with a deprecation warning and migration guide.
- Pre-1.0 releases (0.1.x–0.4.x) receive no more fixes. Users must upgrade.

### Not done in 1.0.0 (explicitly, for later)
- **External security audit** — the `SECURITY.md` process is in place, but the audit itself needs a human engagement. Reserved in the release checklist as a gate for any subsequent v1.x.0 that meaningfully widens the attack surface (voice, SSH, secrets vault — all Phase 2.5+).
- **Voice + multi-server execution** — this is Phase 1.1 (was 2.5 in the pre-freeze roadmap). Will ship as **v1.1.0**.
- **Discord adapter** — still gated on demand signal per the roadmap. Adding it later is a ~100-line exercise because of the `ReplyChannelContract` tests.
- **Web dashboard** — still deferred. The chat *is* the interface.

### Migration from v0.4.0 → v1.0.0

No code changes required. Your existing `config.yaml`, your `.env`, your SQLite database, your systemd unit — all keep working. Run:

```bash
pip install -U datronis-relay
datronis-relay
```

You may want to:

1. Read [`versioning.md`](./versioning.md) so you know what the SemVer contract now commits us to.
2. Read [`api_reference.md`](./api_reference.md) so you know which symbols you're allowed to import safely in external code.
3. Set up the GitHub workflows in `.github/workflows/` if you're running a fork — they are opt-in (you need to enable GitHub Pages and configure PyPI trusted publishing yourself).

---

## [0.4.0] — 2026-04-11

### Added
- **File attachments** on Telegram and Slack. The adapter downloads any document/photo (up to `attachments.max_bytes_per_file`, default 10 MB) to `attachments.temp_dir`, attaches a `FileAttachment` record to the `PlatformMessage`, and the Claude client lists the absolute path in the prompt so Claude uses its `Read` tool to inspect the content. One code path covers text files, PDFs, and images — Claude's `Read` tool is multimodal-aware, so vision works without a second pipeline. Cleanup happens in `MessagePipeline`'s `finally` block on every message, even on failure.
- **`/schedule`, `/schedules`, `/unschedule` commands.** Interval format is `30s`, `5m`, `2h`, `1d` — no cron. Minimum 30s, max 90 days, capped to `scheduler.max_tasks_per_user` per user (default 50).
- **Background scheduler worker** (`core/scheduler.py`). Polls every `scheduler.poll_interval_seconds` (default 30s), atomically claims up to `scheduler.batch_limit` due tasks, and dispatches each as a fire-and-forget asyncio task. Each dispatch reuses `MessagePipeline.process(synthetic_message, channel)` — scheduled tasks go through the exact same auth / rate-limit / cost-tracking / error-mapping path as realtime messages.
- **`AdapterRegistry`** + a new `ChatAdapterProtocol.build_reply_channel(channel_ref)` requirement. Every adapter knows how to reconstruct a `ReplyChannel` from a stored platform-specific ref, so the scheduler can fire to arbitrary Telegram chats or Slack channels without holding a live context object.
- **`TelegramBotReplyChannel`** and **`SlackChannelReplyChannel`** — the bot-driven / client-driven counterparts of the message-bound reply channels, used by the scheduler.
- **SQLite migration `0002_scheduled_tasks.sql`**. New table with indexes on `(is_active, next_run_at)` and `(user_id)`.
- **`SchedulerConfig`** and **`AttachmentsConfig`** in `config.py`. Both on by default; attachments default to 10 MB per file in `./data/attachments`.
- **`PlatformMessage.channel_ref`** (default `""`) — platform-specific reply channel identifier stored with every scheduled task.
- **`PlatformMessage.attachments`** (default `()`) — tuple of `FileAttachment`s the pipeline must clean up.
- **New tests**:
  - `tests/unit/test_interval_parser.py` — happy path, boundary checks, invalid formats, round-trip with `format_interval`.
  - `tests/unit/test_scheduler.py` — tick with no tasks, single due task fires through pipeline + adapter, unknown platform dropped, future tasks untouched.
  - `tests/unit/test_schedule_commands.py` — `/schedule` happy path, invalid interval, below-min interval, missing prompt, per-user cap, no store → disabled message, no channel_ref rejected, `/schedules` list, `/unschedule` with cross-user isolation.
  - Scheduled-task section added to `tests/integration/test_sqlite_storage.py` — real SQLite CRUD + claim-due atomic advance.

### Changed
- **`CommandRouter.__init__`** gained an optional `scheduled_store: ScheduledTaskStoreProtocol | None = None`. Existing Phase 2/3 router construction still works — a `None` store makes the `/schedule*` commands return a "disabled" message instead of raising.
- **`TelegramAdapter.__init__`** gained `attachments_temp_dir` and `max_attachment_bytes` parameters (both with sensible defaults).
- **`SlackAdapter.__init__`** gained the same two parameters.
- **`ChatAdapterProtocol`** now requires `build_reply_channel(channel_ref) -> ReplyChannel`. Both TelegramAdapter and SlackAdapter implement it.
- **`TelegramReplyChannel` file** now also exports `TelegramBotReplyChannel` alongside the existing chat-bound one.
- **`SlackReplyChannel` file** now also exports `SlackChannelReplyChannel`.

### Not done (intentionally)
- **Discord adapter.** Roadmap §4 explicitly gates it on "3+ users request it — data-driven." Adding it speculatively is the exact solo-maintainer-burnout anti-pattern the roadmap's §8 risks table calls out. The Phase 3 `ReplyChannelContract` means adding Discord later is ~100 lines — a subclass + bolt wiring + subscribe it to the contract tests. No infrastructure debt is being accumulated by the skip.

### Dependencies
- **No new top-level dependencies.** Slack's file download uses `aiohttp` directly, which was already a transitive dep of `slack-bolt`. Telegram file download uses `python-telegram-bot`'s built-in `download_to_drive`.

---

## Migration from v0.3.0 → v0.4.0

### 1. Upgrade (no new deps)

```bash
pip install -e ".[dev]"
```

### 2. Let the migration run

On first startup, `0002_scheduled_tasks.sql` creates the `scheduled_tasks` table. Idempotent via the `schema_version` row added in Phase 2.

### 3. (Optional) Tweak the new config sections

Your existing `config.yaml` still works — `scheduler` and `attachments` both have sensible defaults (`scheduler.enabled=true`, `attachments.enabled=true`, 10 MB file cap, `./data/attachments` temp dir). Edit them if you need a higher cap or a different temp location.

### 4. (Optional, important for file uploads) Make sure user allowlists include Read

File attachments work by telling Claude "here's a file at /tmp/.../foo.pdf — use your Read tool." If a user has a restrictive `allowed_tools` that excludes `"Read"`, file uploads silently fail (Claude won't have the tool). Either:
- leave `allowed_tools: []` (empty means no restriction), OR
- explicitly include `"Read"` in the list.

### 5. Try the new features

```
/schedule 5m run sanity checks
/schedules
/unschedule 1
```

Send any file or image in Telegram — the bot will process it. Same in Slack.

### What NOT to do

- Don't set `scheduler.poll_interval_seconds` below a few seconds unless you're testing — the scheduler holds an open SQLite write transaction during `claim_due_tasks`, and extremely aggressive polling fights the rest of the pipeline for the write lock.
- Don't set `max_scheduled_tasks_per_user` to `0` thinking it means "unlimited" — pydantic's `ge=1` validator will reject it at config load. Use a large number if you truly want no cap.
- Don't commit your `./data/attachments` temp dir — the `.gitignore` already covers `data/**`, but double-check on custom paths.

---

## [0.3.0] — 2026-04-11

### Added
- **Slack adapter** via Bolt Socket Mode (`src/datronis_relay/adapters/slack/`). Handles `app_mention` and `message.im` events; strips bot mentions; ignores bot-originated events to prevent loops.
- **`core/reply_channel.py`** — new `ReplyChannel` protocol. Every adapter now provides a `max_message_length`, `send_text()`, and `typing_indicator()` context manager. Keeps cross-platform logic in one place.
- **`core/message_pipeline.py`** — new `MessagePipeline` class that owns the complete inbound → reply flow (correlation binding, auth, dispatch, delivery, error mapping, cleanup). Telegram and Slack both go through it — no copy-paste.
- **Multi-adapter runner** in `main.py` — boots every enabled adapter concurrently. Fail-loud: if any adapter crashes, all others are cancelled and the process exits for the supervisor to restart.
- **`SlackConfig`** in `infrastructure/config.py`. New env overrides `DATRONIS_SLACK_BOT_TOKEN` / `DATRONIS_SLACK_APP_TOKEN` also flip `slack.enabled` to true automatically.
- **`TelegramConfig.enabled`** field (defaults to `true` — pre-existing Phase 2 configs still work).
- **`docs/slack_setup.md`** — full Slack-app setup walkthrough (scopes, Socket Mode, user id, tokens, troubleshooting).
- **Shared `ReplyChannel` contract tests** in `tests/unit/test_reply_channels.py`. Every channel implementation runs the same abstract suite — new adapters get free regression coverage.
- **`tests/unit/test_message_pipeline.py`** — 13 cases for the pipeline itself (static, stream, empty stream, auth fail, rate limit, send-failure-in-error-path, context-var hygiene).
- **`tests/unit/test_slack_adapter.py`** — unit tests for the pure helpers (`_strip_mention`, `_is_bot_event`, `_event_to_platform_message`).
- **`tests/unit/test_chunking.py`** extended with Slack-sized (38k) and very-narrow (200) limit cases.

### Changed — **breaking**
- **`TelegramAdapter.__init__(token, router, auth)`** → **`TelegramAdapter.__init__(token, pipeline)`**. Authentication and routing moved into `MessagePipeline`, which is what the adapter now holds. Composition-root-only change — no user code calls this directly.
- **`TelegramAdapter` shrank** from ~170 lines to ~80. All the business logic (auth, dispatch, chunking, error mapping, typing indicator orchestration) now lives in `MessagePipeline` + `TelegramReplyChannel`.
- **`chunk_message(text, limit)`** is now driven by the channel's own `max_message_length` (Telegram: 4000, Slack: 38000). Previously the pipeline hardcoded 4000, which was a Telegram leak into the core.

### Dependencies
- Added `slack-bolt>=1.18,<2`. Pulls in `slack-sdk` transitively.

### Security
- Socket Mode means no inbound HTTP port is opened for Slack, same way Telegram uses long-polling. No public webhook URL, no TLS certificate to manage. The attack surface doesn't widen meaningfully with the new adapter.
- Channel messages in Slack are intentionally dropped unless they are a DM or a direct bot mention — so a chat-ops bot can't be triggered by ambient conversation in a channel it's been invited to. Documented in `docs/slack_setup.md` §8.

---

## Migration from v0.2.0 → v0.3.0

### 1. Upgrade dependencies

```bash
pip install -e ".[dev]"
```

New runtime dep: `slack-bolt`. No removals.

### 2. Add the `slack` block to `config.yaml` (optional)

If you're only running Telegram, you don't need to change anything — the `slack:` block defaults to `enabled: false`. Your existing Phase 2 `config.yaml` still works.

If you want to enable Slack, add:

```yaml
slack:
  enabled: true
  bot_token: "xoxb-..."
  app_token: "xapp-..."
```

…or keep the tokens in env vars (recommended):

```env
DATRONIS_SLACK_BOT_TOKEN=xoxb-...
DATRONIS_SLACK_APP_TOKEN=xapp-...
```

Setting either env var automatically flips `slack.enabled` to true — no YAML edit required.

### 3. Add Slack users to your allowlist

Slack user ids are namespaced `slack:U...`. Follow `docs/slack_setup.md` §5 to find yours, then:

```yaml
users:
  - id: "slack:U0XXXXXXX"
    display_name: "Me (Slack)"
    allowed_tools: ["Read", "Bash"]
    rate_limit:
      per_minute: 20
      per_day: 1000
```

A single user who chats the bot on both Telegram and Slack needs **two** entries (one per platform) — namespaced ids are not unified across platforms.

### 4. Walk through `docs/slack_setup.md`

Create the Slack app, enable Socket Mode, add scopes, install to workspace, copy both tokens, subscribe to `app_mention` and `message.im`. Expect ~10 minutes end-to-end.

### 5. Run

```bash
datronis-relay
```

Two log lines on startup confirm which adapters loaded:

```json
{"event": "adapter.enabled", "adapter": "telegram"}
{"event": "adapter.enabled", "adapter": "slack"}
```

### What NOT to do
- Don't construct `TelegramAdapter(token, router, auth)` anywhere in your own code — the signature is `(token, pipeline)` now. Rebuild via the composition root pattern in `main.py`.
- Don't assume the Slack adapter supports formatting — v0.3 sends plain text. Claude's `**bold**` will render literally in Slack until Phase 4 adds per-platform formatting.
- Don't forget to **reinstall** the Slack app after adding scopes or events — Slack requires a fresh install for new permissions.

---

## [0.2.0] — 2026-04-11

### Added
- **SQLite persistence** (`aiosqlite` + WAL) for sessions, audit log, and cost ledger. Schema applied on startup via numbered migrations in `infrastructure/migrations/`.
- **Multi-user allowlist** loaded from a YAML `config.yaml`. Each user carries `allowed_tools`, `rate_limit.per_minute`, `rate_limit.per_day`.
- **`RateLimiter`** — per-user two-bucket token limiter (per-minute + per-day), in-memory, serialized via a lock. Daily exhaustion refunds the minute token.
- **`CostTracker`** — pricing table in YAML, computes USD from token counts, rolls up per `(day, user_id)` in the `cost_ledger` table.
- **`/cost`** command — reports today / 7d / 30d / total token counts and spend.
- **Per-user tool allowlist** — forwarded to `ClaudeAgentOptions.allowed_tools` per request.
- **`StreamEvent` protocol** — `ClaudeClientProtocol.stream()` now yields `TextChunk | CompletionEvent`; usage is extracted from the terminal `CompletionEvent` and recorded by the router.
- **Prometheus metrics** (opt-in) — `datronis_messages_total`, `datronis_claude_tokens_total`, `datronis_claude_cost_usd_total`, `datronis_dispatch_duration_seconds`. Exposed via `prometheus_client.start_http_server` when `metrics.enabled: true`.
- **Audit log** — every Claude call and auth decision can be recorded as an `AuditEntry` via `AuditStoreProtocol`.
- **`docs/security.md`** — STRIDE threat model for the Phase 2 surface.
- **New tests**:
  - `tests/unit/test_rate_limiter.py`
  - `tests/unit/test_cost_tracker.py`
  - `tests/integration/test_sqlite_storage.py` (real SQLite, temp dir per test)
  - `tests/integration/test_load.py` (100 concurrent dispatches + rate-limit stress)

### Changed — **breaking**
- **Config format** — env-only `Settings` is removed. Configuration now lives in a YAML file at `./config.yaml` (override with `DATRONIS_CONFIG_PATH`). Secrets (`DATRONIS_TELEGRAM_BOT_TOKEN`, `ANTHROPIC_API_KEY`) remain in env vars and override YAML values.
- **User id format** — all user ids are now namespaced `"<platform>:<platform_uid>"`. Example: `telegram:123456789`. The Telegram adapter builds this shape automatically; YAML `users[].id` must match.
- **`AuthGuard.check(message)` → `AuthGuard.authenticate(message) -> User`**. Callers now receive the resolved `User` record and pass it to `CommandRouter.dispatch(message, user)`.
- **`CommandRouter.__init__`** now requires `rate_limiter: RateLimiter` and `cost_tracker: CostTracker` in addition to `claude` and `sessions`.
- **`ClaudeClientProtocol.stream(request)`** returns `AsyncIterator[StreamEvent]` instead of `AsyncIterator[str]`. `FakeClaude` in tests now yields `TextChunk` + a terminal `CompletionEvent`.
- **`ClaudeRequest`** gains `allowed_tools: tuple[str, ...]` (default empty tuple = no restriction). Serialized order is sorted alphabetically for determinism.
- **`pydantic-settings`** dependency removed. Replaced by PyYAML + plain pydantic `BaseModel`.

### Fixed
- **Race in `SessionManager.get_or_create`** under concurrent calls for the same user — now protected by a per-user `asyncio.Lock`. (Already in Phase 1, but the concurrency test in `test_load.py` now exercises it with 100 concurrent askers.)

### Security
- Secrets can now be kept entirely out of `config.yaml` by using env vars — no more shipping `DATRONIS_ALLOWED_TELEGRAM_USER_ID` alongside the token.
- SQLite opens with `PRAGMA foreign_keys=ON` and `journal_mode=WAL` for crash safety.
- STRIDE threat model documented in `docs/security.md`; next audit due before the Phase 2.5 release.

---

## Migration from v0.1.0 → v0.2.0

Phase 1 ran on env vars only. Phase 2 requires a YAML config. Step-by-step:

### 1. Install new dependencies

```bash
pip install -e ".[dev]"
```

New runtime deps: `aiosqlite`, `PyYAML`, `prometheus-client`. `pydantic-settings` is removed.

### 2. Create `config.yaml`

```bash
cp config.example.yaml config.yaml
```

Edit it and:
- put your Telegram bot token under `telegram.bot_token` (or keep it in the env as `DATRONIS_TELEGRAM_BOT_TOKEN`),
- add your namespaced user id under `users[].id`. If your Phase 1 value was `DATRONIS_ALLOWED_TELEGRAM_USER_ID=123456789`, your new id is `telegram:123456789`,
- add per-user `allowed_tools` and `rate_limit`,
- add model pricing under `cost.pricing`.

### 3. Update `.env`

Remove `DATRONIS_ALLOWED_TELEGRAM_USER_ID` and all the non-secret `DATRONIS_*` vars that moved to YAML. Keep only:

```env
DATRONIS_TELEGRAM_BOT_TOKEN=...
ANTHROPIC_API_KEY=...
```

### 4. Create the SQLite directory

```bash
mkdir -p data
```

(Or set `storage.sqlite_path` to an existing writable location. The parent directory is auto-created on startup.)

### 5. Run

```bash
datronis-relay
```

On first startup, migration `0001_init.sql` is applied and the `schema_version` row is inserted. Subsequent starts are idempotent.

### 6. Verify

- Send `/help` to your bot → the list now includes `/cost`.
- Send a prompt → after the reply, send `/cost` → numbers should be non-zero.
- Restart the bot → send `/status` → session id should be **the same** as before the restart (Phase 2 persistence).

### What NOT to do

- Don't try to keep the Phase 1 `AuthGuard.check()` call sites — they won't compile. The method is gone; use `authenticate()`.
- Don't put secrets in `config.yaml` if you commit it to version control. Keep them in env.
- Don't stream text chunks through the Claude client assuming `AsyncIterator[str]` — the new event protocol means you must handle `TextChunk` vs `CompletionEvent`.

---

## [0.1.0] — 2026-04-10

Initial Phase 1 MVP:
- Telegram long-polling adapter
- Single-user env-based allowlist
- In-memory sessions
- Claude Agent SDK integration, streaming, typing indicator, message chunking
- Structured JSON logs with correlation IDs
- Dockerfile + docker-compose + systemd unit + quickstart docs
