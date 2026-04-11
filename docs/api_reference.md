# API Reference

v1.0.0 is a SemVer commitment: the public surface listed on this page is guaranteed stable for the entire **1.x** major series. Breaking changes will require v2.0.0.

This page is the **single source of truth** for what "public" means. Anything not listed here is **internal** — it may change in a minor release without warning.

## How to read this page

- **Public** — guaranteed stable under [SemVer](./versioning.md).
- **Public (protocol)** — the shape is stable, but adding new methods is non-breaking for consumers that don't implement the protocol.
- **Internal** — `_`-prefixed, or explicitly listed under the "Not public" sections below. May change in any release.

## Domain layer — `datronis_relay.domain`

All domain types are frozen dataclasses. They are the contracts between layers. Constructing them is part of the public API; mutating their fields is impossible by design.

### Public

| Symbol | Module | Notes |
|---|---|---|
| `UserId`, `SessionId`, `CorrelationId` | `domain.ids` | `NewType[str]`. Construct via the constructors; don't parse. |
| `new_session_id()`, `new_correlation_id()` | `domain.ids` | Factory functions. |
| `Platform` (enum: `TELEGRAM`, `SLACK`, `DISCORD`) | `domain.messages` | New variants may be added in minors — consumers must handle the default case. |
| `MessageKind` (enum: `TEXT`, `VOICE`) | `domain.messages` | `VOICE` is reserved for Phase 1.1. |
| `PlatformMessage` | `domain.messages` | Fields: `correlation_id`, `platform`, `user_id`, `text`, `kind`, `received_at`, `attachments`, `channel_ref`. New fields with defaults are non-breaking. |
| `ClaudeRequest` | `domain.messages` | Fields: `correlation_id`, `session_id`, `user_id`, `prompt`, `allowed_tools`, `attachments`. |
| `ClaudeResponse` | `domain.messages` | Reserved for future use. Shape is stable. |
| `User` | `domain.user` | Fields: `id`, `display_name`, `allowed_tools`, `rate_limit_per_minute`, `rate_limit_per_day`. |
| `FileAttachment` | `domain.attachments` | Fields: `path`, `filename`, `mime_type`, `size_bytes`. Method: `is_image()`. |
| `StreamEvent = TextChunk \| CompletionEvent` | `domain.stream_events` | Discriminated union. `Usage` with `tokens_in`, `tokens_out`, `cost_usd`. |
| `AuditEntry`, `AuditEventType` | `domain.audit` | Append-only record shape. |
| `CostSummary` | `domain.cost` | Fields: `today_*`, `week_cost_usd`, `month_cost_usd`, `total_cost_usd`. |
| `ModelPricing` | `domain.pricing` | With the `cost(tokens_in, tokens_out)` method. |
| `ScheduledTask` | `domain.scheduled_task` | Fields: `id`, `user_id`, `platform`, `channel_ref`, `prompt`, `interval_seconds`, `next_run_at`, `created_at`, `is_active`. |
| `RelayError`, `AuthError`, `RateLimitError`, `ClaudeApiError`, `RelayTimeoutError`, `InternalError`, `NotImplementedCommand`, `ErrorCategory` | `domain.errors` | Exception hierarchy + `user_message()` method. |

## Core layer — `datronis_relay.core`

### Public (classes)

| Symbol | Module | Purpose |
|---|---|---|
| `AuthGuard(users)` | `core.auth` | `authenticate(message) -> User` |
| `SessionManager(store)` | `core.session_manager` | `get_or_create(user_id)`, `reset(user_id)` |
| `CommandRouter(claude, sessions, rate_limiter, cost_tracker, scheduled_store=None, max_scheduled_tasks_per_user=50)` | `core.command_router` | `dispatch(message, user) -> StaticReply \| StreamReply` |
| `StaticReply`, `StreamReply`, `Reply` | `core.command_router` | Reply value objects. |
| `RateLimiter()` | `core.rate_limiter` | `check(user_id, per_minute, per_day)` |
| `CostTracker(store, pricing, default_model)` | `core.cost_tracker` | `record(user_id, tokens_in, tokens_out)`, `summary(user_id)` |
| `MessagePipeline(auth, router)` | `core.message_pipeline` | `process(message, channel)` — the heart of the project. |
| `Scheduler(store, pipeline, registry, poll_interval_seconds=30.0, batch_limit=10)` | `core.scheduler` | `run_forever()`, `tick()` |
| `AdapterRegistry(adapters)` | `core.scheduler` | Platform → adapter lookup. |
| `chunk_message(text, limit)` | `core.chunking` | Message-chunking helper. Keeps adapters platform-specific about their limits. |
| `parse_interval(text)`, `format_interval(seconds)` | `core.interval_parser` | Schedule interval parsing. Constants: `MIN_INTERVAL_SECONDS = 30`, `MAX_INTERVAL_SECONDS = 90 * 86_400`. |

### Public (protocols)

Every port is a `typing.Protocol`. Implement them to plug in new behavior; the core depends on the protocol, not the implementation.

| Protocol | Module | Purpose |
|---|---|---|
| `ClaudeClientProtocol` | `core.ports` | Wraps the Agent SDK. Yields `StreamEvent`s. |
| `SessionStoreProtocol` | `core.ports` | Per-user session CRUD. |
| `AuditStoreProtocol` | `core.ports` | Append-only audit writer. |
| `CostStoreProtocol` | `core.ports` | Cost ledger reader + writer. |
| `ScheduledTaskStoreProtocol` | `core.ports` | Scheduled task CRUD + atomic claim. |
| `ReplyChannel` | `core.reply_channel` | Platform-agnostic send interface. Required attributes/methods: `max_message_length: int`, `async send_text(text)`, `typing_indicator() -> AbstractAsyncContextManager[None]`. |

## Infrastructure layer — `datronis_relay.infrastructure`

### Public

| Symbol | Module | Notes |
|---|---|---|
| `AppConfig`, `AppConfig.load(path=None)` | `infrastructure.config` | YAML config loader. See [quickstart](./quickstart.md) for the shape. |
| `TelegramConfig`, `SlackConfig`, `ClaudeConfig`, `StorageConfig`, `LoggingConfig`, `MetricsConfig`, `SchedulerConfig`, `AttachmentsConfig`, `UserConfig`, `RateLimitConfig`, `CostConfig`, `ModelPricingEntry` | `infrastructure.config` | Pydantic models. Adding new optional fields is non-breaking. |
| `SQLiteStorage(path)` with `.open()`, `.close()`, and the four store protocol methods | `infrastructure.sqlite_storage` | Implements all four store protocols. |
| `InMemorySessionStore()` | `infrastructure.session_store` | Test-only; kept public because users may want it for their own tests. |
| `configure_logging(level, json_output)`, `bind_correlation(cid)`, `clear_correlation()` | `infrastructure.logging` | Structlog setup. |
| `start_metrics_server(host, port)`, and the `MESSAGES_TOTAL`, `CLAUDE_TOKENS_TOTAL`, `CLAUDE_COST_USD_TOTAL`, `DISPATCH_DURATION_SECONDS` counters | `infrastructure.metrics` | Prometheus. Label sets on the counters are stable. |

### Not public

- `ClaudeAgentClient` — **internal**. The Claude Agent SDK surface evolves, and this wrapper is explicitly designed so upgrades touch one file. Use the `ClaudeClientProtocol` in your own composition if you need to swap it.
- Everything under `_`-prefixed names inside public modules (e.g. `_Bucket`, `_cleanup_attachments`, `_TelegramBotTypingIndicator`) — internal.
- SQLite migration file names and the `schema_version` bookkeeping — internal. Your code must not query `scheduled_tasks` directly; go through the protocol.

## Adapters — `datronis_relay.adapters`

### Public

| Symbol | Module | Notes |
|---|---|---|
| `TelegramAdapter(token, pipeline, attachments_temp_dir, max_attachment_bytes)` | `adapters.telegram.bot` | Implements `ChatAdapterProtocol`. |
| `TelegramReplyChannel(chat)`, `TelegramBotReplyChannel(bot, chat_id)` | `adapters.telegram.reply_channel` | Both implement `ReplyChannel`. |
| `SlackAdapter(bot_token, app_token, pipeline, attachments_temp_dir, max_attachment_bytes)` | `adapters.slack.bot` | Implements `ChatAdapterProtocol`. |
| `SlackReplyChannel(say)`, `SlackChannelReplyChannel(client, channel_id)` | `adapters.slack.reply_channel` | Both implement `ReplyChannel`. |
| Every adapter's `run_forever() -> None` and `build_reply_channel(channel_ref) -> ReplyChannel` | structural contract | Required for multi-adapter runner and scheduler. |

### Not public

- Anything underscore-prefixed (`_strip_mention`, `_event_to_platform_message`, `_to_platform_message`, etc.) — tested, but not guaranteed to stay at their current module locations.
- The `SUPPORTED_COMMANDS` tuple in each adapter — internal dispatch helper.

## Composition root — `datronis_relay.main`

**`main.py` is internal.** It's the reference composition, not a public API. If you're embedding datronis-relay in a larger application, build your own composition root — everything it imports is public.

The `main()` function is exposed for the `datronis-relay` console script entry point. Calling it programmatically is supported but you can't pass arguments to it.

## Stability guarantees

Under SemVer (see [versioning.md](./versioning.md)):

- **Patch (1.0.x)**: bug fixes only. No new features, no config-schema changes, no signature changes.
- **Minor (1.x.0)**: new features, new optional config fields, new adapters. Existing public symbols retain their signatures. New methods may be added to Protocols if they are adding capabilities the core doesn't require by default.
- **Major (2.0.0)**: removal or rename of any symbol on this page. Requires a migration guide with a one-minor-cycle deprecation window (see `versioning.md`).

## I need to do X and I don't see it here

If you're building on datronis-relay and your use case requires reaching into an internal symbol:

1. **Open a discussion** describing what you need and why.
2. If it's reasonable, we'll promote the symbol to public in the next minor.
3. If not, we'll suggest an alternative or a cleaner composition.

Do not rely on internal symbols — they will break, and the changelog will not mention it.
