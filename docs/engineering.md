# Engineering

This page covers what the project demonstrates as a body of engineering
work — the achievements snapshot at the top, followed by a catalogue of
real bugs hit during development and how they were resolved.

## 🏆 Key achievements

A snapshot of what this project demonstrates as a portfolio piece.

| # | Achievement | Evidence |
|---|---|---|
| 1 | **Clean Architecture** with strict dependency inversion — 4 layers (Domain → Core → Infrastructure → Adapters). Zero cycles. Adapters never import `core/` internals; infrastructure only talks to the core through Protocols. | `src/datronis_relay/{domain,core,infrastructure,adapters}/` + `grep` proof: zero `from datronis_relay.core.auth` imports inside `adapters/` |
| 2 | **Multi-platform chat front-end** via a shared `MessagePipeline` — Telegram long-polling + Slack Bolt Socket Mode running **concurrently** from a single Python process. | `core/message_pipeline.py`, `adapters/telegram`, `adapters/slack`, `main._run_until_stopped` |
| 3 | **High-performance async pipeline** — **p50 ~0.5 ms / p95 ~1.2 ms** pure-dispatch latency; sustained **~15,000 dispatches/sec** at 100 concurrent users on an M-series laptop. | `scripts/benchmark.py`, `docs/performance.md` |
| 4 | **Persistent SQLite state** — `aiosqlite` + WAL journal mode, numbered schema migrations on startup, **4 tables / 5 indexes**, atomic task claiming. | `infrastructure/sqlite_storage.py`, `migrations/000*.sql` |
| 5 | **120+ tests** across **unit / integration / contract / load** categories. `mypy --strict` clean. `ruff` clean. Coverage target **≥ 80 %** enforced via `coverage.report.fail_under`. | `tests/`, `pyproject.toml` |
| 6 | **Cost governance built in** — per-user token-bucket rate limiter (per-minute + per-day), pricing-aware USD cost ledger, `/cost` command for today / 7d / 30d / total. | `core/rate_limiter.py`, `core/cost_tracker.py`, `command_router._handle_schedule` |
| 7 | **Background scheduler** that fires recurring tasks through the **same** `MessagePipeline` as realtime messages — zero duplication of auth, rate-limiting, cost tracking, or error mapping. | `core/scheduler.py` + `AdapterRegistry` pattern |
| 8 | **File and image attachments** — one `FileAttachment` type covers PDFs, code files, and images; temp files cleaned up in the pipeline's `finally` block regardless of success path. | `domain/attachments.py`, `core/message_pipeline._cleanup_attachments` |
| 9 | **SemVer-committed public API** — `docs/api_reference.md` is the single source of truth for what's stable vs internal, backed by `docs/versioning.md` with explicit breaking/non-breaking tables. | `docs/api_reference.md`, `docs/versioning.md` |
| 10 | **Production packaging** — PEP 517 build (hatchling), multi-stage Docker image, **hardened systemd unit** (NoNewPrivileges, ProtectSystem=strict, MemoryDenyWriteExecute), GitHub Actions CI/CD with trusted PyPI publishing. | `Dockerfile`, `examples/systemd/*.service`, `.github/workflows/*.yml` |
| 11 | **STRIDE threat model** with a per-threat `Gaps` column, private security reporting flow, 90-day key rotation guidance. | `docs/security.md`, `SECURITY.md` |
| 12 | **Published documentation site** — mkdocs-material, auto-deployed to GitHub Pages via a `--strict` build on every push to `main`. | `mkdocs.yml`, `.github/workflows/docs.yml` |
| 13 | **Next.js 15 admin dashboard** — App Router, React 19, Radix UI Themes, Tailwind CSS 4, next-intl, TypeScript strict mode. Clean separation into `lib/` (schemas + API client), `components/` (presentational), `hooks/` (data), `app/` (routes). Zero `any` in the codebase. | `ui/src/`, `ui/tsconfig.json` |
| 14 | **108 UI unit tests across 10 files** — zod schema validation, CSV export, interval helpers, locale key-parity, RTL infrastructure. `pnpm typecheck` / `pnpm lint` / `pnpm build` all clean. Every page under the **250 KB first-load JS** KPI. | `ui/tests/unit/`, `ui/package.json` |
| 15 | **6 locales with enforced key-tree parity** — English, German, Spanish, French, Simplified Chinese, Japanese. Every translation has the same key set, locked down by `locale-parity.test.ts` so a missing key in any locale fails CI. `next-intl` App Router + RTL infrastructure ready for future `ar` / `he`. | `ui/messages/*.json`, `ui/tests/unit/locale-parity.test.ts` |
| 16 | **Interactive CLI setup wizard** — `datronis-relay setup` auto-installs the Claude Code native binary, prompts for tokens, generates `config.yaml`, installs a hardened systemd unit, runs `claude login` with a terminal-side QR code so the OAuth URL is easy to copy from headless servers. `datronis-relay doctor` validates an existing config. | `src/datronis_relay/cli/setup.py`, `src/datronis_relay/cli/doctor.py` |

---

## 🚧 Engineering challenges & solutions

Real problems hit during development and how they were resolved. Each
item includes symptom, root cause, chosen fix, and the test that now
pins the invariant.

### 1. Race condition in `SessionManager.get_or_create`

- **Symptom:** two concurrent messages from the same user could create duplicate session rows — one of them would "win" the `SELECT`, both would `INSERT`, and the audit log would record two sessions for a single conversation.
- **Root cause:** classic check-then-act between `store.get` and `store.set`. The store's internal lock only protected each call individually, not the sequence.
- **Fix:** added a **per-user `asyncio.Lock` map**, guarded by a single `_locks_guard` lock to prevent torn dictionary writes. `get_or_create` now acquires the user's lock for the full check-then-act sequence. Per-user granularity means unrelated users never block each other.
- **Verification:** `tests/unit/test_session_manager.py::test_session_store_is_concurrency_safe` — 20 concurrent `get_or_create` calls for the same user must all return the same session id.

### 2. Telegram leakage into `core/`

- **Symptom:** `DEFAULT_LIMIT = 4000` lived in `core/chunking.py`. That's Telegram's hard cap minus a margin — Slack's cap is ~40,000. Using 4000 for Slack meant sending 10× as many messages as necessary.
- **Root cause:** an adapter-specific constant leaked into the platform-agnostic core during Phase 1, when Telegram was the only adapter.
- **Fix:** added a `max_message_length: int` attribute to the `ReplyChannel` protocol. Each adapter defines its own limit (`TELEGRAM_MAX_MESSAGE_LENGTH = 4000`, `SLACK_MAX_MESSAGE_LENGTH = 38000`). The pipeline reads `channel.max_message_length` at call time; `chunk_message` accepts the limit as a parameter (it already did — just wasn't being used).
- **Verification:** `tests/unit/test_chunking.py::test_custom_larger_limit_slack_sized` and `tests/integration/test_pipeline.py::test_pipeline_respects_channel_max_message_length`.

### 3. Usage data lost in the stream API

- **Symptom:** the Phase 1 `ClaudeClientProtocol.stream()` yielded `str`. Usage metadata from the SDK's final `ResultMessage` had nowhere to go — cost tracking was impossible.
- **Root cause:** the original abstraction was too narrow. The stream's primary output is text, but its terminal output is a usage summary — both need to flow out.
- **Fix:** refactored the protocol to yield `StreamEvent = TextChunk | CompletionEvent`, a discriminated union. The router wraps the underlying stream with `_text_stream(events, user)` that yields just text to the adapter and consumes `CompletionEvent` into the cost tracker as a side effect — so the adapter still sees `AsyncIterator[str]`, no ripple.
- **Verification:** `tests/unit/test_command_router.py::test_completion_event_is_recorded_to_cost_store`.

### 4. Scheduler needs to deliver without a live chat context

- **Symptom:** a scheduled task fires at 3 AM. The user is asleep, no inbound message arrives — but the bot needs to post the result to the chat the user originally scheduled from.
- **Root cause:** the adapter's `ReplyChannel` is built from an active `Chat` object that only exists during an inbound event handler.
- **Fix:** added `ChatAdapterProtocol.build_reply_channel(channel_ref: str) -> ReplyChannel`. Telegram reconstructs via `TelegramBotReplyChannel(bot, chat_id)`. Slack reconstructs via `SlackChannelReplyChannel(client, channel_id)`. The scheduler stores a platform-specific `channel_ref` per task and calls `adapter.build_reply_channel(ref)` at fire time, then passes the channel to the same `MessagePipeline.process()` used for realtime messages.
- **Verification:** `tests/unit/test_scheduler.py::test_due_task_is_dispatched_through_pipeline`.

### 5. Slack file download reaching into `slack_sdk` private internals

- **Symptom:** my first pass used `slack_sdk._request_aiohttp_session` to authenticate the download. That's a private method that changes between minor versions.
- **Root cause:** `slack_sdk.AsyncWebClient` doesn't expose a public raw-GET helper for `url_private` downloads.
- **Fix:** switched to **`aiohttp.ClientSession` directly** with a manual `Authorization: Bearer <bot_token>` header. `aiohttp` is already a transitive dependency of `slack-bolt`, so no new direct dep is introduced. Zero reliance on private APIs, works across slack-sdk versions.
- **Verification:** adapter code review + a future CI redaction test on the download path.

### 6. Temp file leakage on error paths

- **Symptom:** an attachment downloaded during an `/ask` could leak to disk if any exception occurred between the download and the Claude stream completing.
- **Root cause:** cleanup was originally inline in the happy path, not a `try/finally`.
- **Fix:** moved cleanup into **`MessagePipeline.process()`'s `finally` block** via `_cleanup_attachments(message)`. The same code path that created the temp file deletes it, always — on success, on auth failure, on rate-limit rejection, on internal exception.
- **Verification:** `tests/unit/test_message_pipeline.py::TestErrorMapping::test_send_failure_in_error_path_is_swallowed` + manual file-count check after each Phase 4 smoke test.

### 7. Context variable leakage between concurrent requests

- **Symptom:** during concurrent update processing, `structlog`'s `correlation_id` could leak from one request's log lines into another's.
- **Root cause:** `python-telegram-bot` with `concurrent_updates=True` spawns asyncio Tasks per update, and I was binding the contextvar at the start of a handler without unbinding in a `finally`.
- **Fix:** `bind_correlation()` is called at the top of `MessagePipeline.process()`, and `clear_correlation()` in the `finally`. Python's asyncio Tasks copy the current context at creation time (PEP 568), so concurrent requests get isolated `contextvars.Context` instances. The `finally` unbinds are belt-and-suspenders.
- **Verification:** `tests/unit/test_message_pipeline.py::TestContextvarHygiene::test_correlation_is_cleared_after_each_call`.

### 8. Rate limiter burning minute budget on daily-cap exhaustion

- **Symptom:** when a user hit their `per_day` limit, the minute token was also consumed — so back-pressure from the daily cap double-charged the user.
- **Root cause:** naive implementation deducted from both buckets unconditionally before checking the daily one.
- **Fix:** **refund the minute token** when the daily bucket is empty. The `_Bucket` is a struct, so the fix is a single `minute_bucket.tokens = min(minute_bucket.capacity, minute_bucket.tokens + 1.0)` line.
- **Verification:** `tests/unit/test_rate_limiter.py::test_daily_exhaustion_refunds_the_minute_token`.

### 9. Claude Agent SDK message-shape drift

- **Symptom:** the SDK's message hierarchy evolves; a naive extractor would break on every minor bump.
- **Fix:** isolated **every** SDK-shape assumption in two private helpers in `infrastructure/claude_client.py`: `_extract_text` and `_extract_usage`. Both use `getattr` + `isinstance` checks, never touch attributes the SDK hasn't documented. When the SDK changes, this is the only file to update. `ClaudeAgentClient` is marked **internal** in `docs/api_reference.md` precisely so upstream consumers can't couple to the shape.
- **Verification:** the entire test suite uses a `FakeClaude` that implements `ClaudeClientProtocol` structurally, so SDK drift cannot break unit tests.

### 10. Adapter pattern anti-leak enforcement

- **Symptom:** in Phase 2, the `TelegramAdapter` contained all pipeline logic (auth, dispatch, chunking, error mapping). Copy-pasting it into `SlackAdapter` would have been the exact "adapters leak into core" failure the roadmap's risks table calls out.
- **Fix:** extracted `MessagePipeline` + `ReplyChannel` Protocol in Phase 3. Now adapters are ~80-line glue — they parse platform events into `PlatformMessage`s and hand both message + channel to the pipeline. A grep across `src/datronis_relay/adapters/` for `from datronis_relay.core.auth` or `from datronis_relay.core.command_router` returns **zero matches** — enforced by code structure.
- **Verification:** `tests/unit/test_message_pipeline.py` (13 pipeline tests) + `tests/unit/test_reply_channels.py` (abstract `ReplyChannelContract` subclassed per adapter).
