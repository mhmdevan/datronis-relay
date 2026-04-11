# datronis-relay

> **Talk to and control your servers from chat platforms. Safely.**

datronis-relay is a self-hosted service that lets authorized users drive a Claude Code agent from chat platforms. A message arrives on Telegram or Slack → a platform adapter parses it → a platform-agnostic core authenticates, rate-limits, routes, and tracks cost → the Claude Agent SDK produces a reply → the reply goes back through the adapter to the user. One bot, many servers, one stable API.

<div class="grid cards" markdown>

- :material-rocket-launch-outline: **[Quickstart](./quickstart.md)** — install, configure, run
- :material-slack: **[Slack setup](./slack_setup.md)** — end-to-end walkthrough
- :material-api: **[API reference](./api_reference.md)** — public surface + stability
- :material-shield-lock: **[Security](./security.md)** — STRIDE threat model
- :material-speedometer: **[Performance](./performance.md)** — benchmarks + methodology
- :material-tag-outline: **[Changelog](./changelog.md)** — every version, every breaking change

</div>

## What's in v1.0.0

- **Multi-platform chat**: Telegram long-polling and Slack Socket Mode, running concurrently from one process.
- **Multi-user allowlist** via `config.yaml` — per-user tool permissions and per-user rate limits.
- **SQLite persistence** — sessions, audit log, cost ledger, scheduled tasks. Schema migrations on startup.
- **Cost tracking** with `/cost` for today / 7d / 30d / total spend in USD.
- **File and image attachments** — Claude reads uploaded files via its `Read` tool. One type, one code path.
- **Scheduled tasks** — `/schedule 1h run the tests` fires through the same pipeline as a realtime message.
- **Clean Architecture** — adapters depend on core, core depends on ports, infrastructure implements them. Adding a new platform is a ~100-line exercise thanks to the shared `MessagePipeline` and `ReplyChannel` protocol.
- **Optional Prometheus metrics** — opt-in, exposed on a configurable port.

## What's next

v1.0.0 is a freeze of the current surface. The next minor (**v1.1.0**) adds voice input via Whisper, a multi-server execution backend (SSH / Docker exec) with per-server permissions, and an age-encrypted secrets vault for server credentials — all under the SemVer commitment documented in [`versioning.md`](./versioning.md).

## License

MIT. See [`LICENSE`](https://github.com/mhmdevan/datronis-relay/blob/main/LICENSE).
