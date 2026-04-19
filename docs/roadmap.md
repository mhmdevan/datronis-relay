# Roadmap status

## Backend (Python bot)

| Phase | Version | Theme | Status |
|---|---|---|---|
| **Phase 0** | — | Scaffolding, CI, licensing, governance | ✅ Complete |
| **Phase 1** | `v0.1.0` | MVP — Telegram, single user, in-memory | ✅ Complete |
| **Phase 2** | `v0.2.0` | Hardening — SQLite, multi-user, rate limit, cost tracking, STRIDE | ✅ Complete |
| **Phase 3** | `v0.3.0` | Multi-platform — Slack, shared `MessagePipeline`, contract tests | ✅ Complete |
| **Phase 4** | `v0.4.0` | Ecosystem — file/image attachments, `/schedule` + background worker | ✅ Complete |
| **Phase 5** | **`v1.0.0`** | **Production — API freeze, SemVer, docs site, performance benchmarks, CI/CD** | ✅ **Current** |
| Phase 1.1 | `v1.1.0` | Voice (Whisper) + multi-server execution (SSH / Docker) + secrets vault | 🚧 Next |
| Phase 1.2 | `v1.2.0` | Ecosystem — Discord (demand-gated), scheduled task retries | 📅 Planned |

## Frontend (Next.js web dashboard)

| Phase | Theme | Status |
|---|---|---|
| **Phase UI-0** | Foundation — Next.js 15 + Radix UI + next-intl + i18n + app shell + login page | ✅ Complete |
| **Phase UI-1** | Dashboard + Users — data flow, zod schemas, typed API client, `useApi` hook, CRUD with dialog + skeleton + error + empty + toast | ✅ Complete |
| **Phase UI-2** | Tasks + Adapters — scheduled task CRUD with interval picker, adapter cards with optimistic toggle + token rotation | ✅ Complete |
| **Phase UI-3** | Cost + Audit — recharts bar chart (lazy-loaded), sortable per-user table, client-side CSV export, audit filters + cursor pagination + expandable rows | ✅ Complete |
| **Phase UI-4** | Settings + Polish — 5-section config form, restart dialog, dirty-aware save, RTL/a11y/bundle-budget verification | ✅ Complete |
| **Phase UI-5** | Backend API — Python REST endpoints for `/api/users`, `/api/tasks`, `/api/adapters`, `/api/cost/*`, `/api/audit`, `/api/config`, `/api/restart` + bearer-token middleware | 🚧 Next |

## Message formatting

| Phase | Theme | Status |
|---|---|---|
| **Phase M-0** | Foundation — `MessageFormatter` port, `mistune` parser, chunker, passthrough fallback | ✅ Complete |
| **Phase M-1** | Telegram HTML renderer — every element, tables → monospace `<pre>`, bidi-safe code blocks | ✅ Complete |
| **Phase M-2** | Slack mrkdwn renderer — single-asterisk bold, `<url\|text>` links, shared chunker | ✅ Complete |
| **Phase M-3** | Polish — `strip_markdown` fallback, long code block splitting with `(part i/n)`, Prometheus counters, `hypothesis` property tests, 14 golden fixtures | ✅ **Complete** |
| **Phase M-4** | Advanced — streaming edits, Discord, LaTeX, per-user formatting mode | 📅 Later |

Per-phase breakdown, Definition-of-Done gates, and KPI targets for the
backend are distilled into per-release sections of
[`changelog.md`](./changelog.md). Frontend and message-formatting phase
details live in internal planning notes.
