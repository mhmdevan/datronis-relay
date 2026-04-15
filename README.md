<div align="center">

# 🤖 datronis-relay

### Run Claude Code from your phone. Stop paying Anthropic twice.

**Self-hosted chat bridge between Telegram/Slack and the Claude Agent SDK — with a Next.js admin dashboard.**

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=next.js&logoColor=white)](./ui)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-~230-success)](./docs/testing.md)
[![mypy strict](https://img.shields.io/badge/mypy-strict-brightgreen)](http://mypy-lang.org/)
[![ruff](https://img.shields.io/badge/lint-ruff-000000?logo=ruff)](https://github.com/astral-sh/ruff)
[![i18n](https://img.shields.io/badge/i18n-6%20locales-4F46E5)](./ui/messages)
[![Docker](https://img.shields.io/badge/Docker-multi--stage-2496ED?logo=docker&logoColor=white)](./Dockerfile)

<!--
DEMO GIF GOES HERE.
Record a 20–30 second screencast: open Telegram → type "explain the last 50 lines
of nginx access log on web-1" → bot streams a formatted reply.
Save as docs/assets/demo.gif, then replace this placeholder block with:
    <img src="docs/assets/demo.gif" alt="datronis-relay demo" width="640">
Recording instructions: docs/assets/README.md
-->

> 🎬 *30-second demo coming soon. See [`docs/assets/README.md`](./docs/assets/README.md) for the recording brief.*

</div>

---

## 💀 Stop paying twice for Claude

You pay Anthropic **$20 a month** for Claude Pro. You install a self-hosted Claude chat bot. It asks for an API key. Your Anthropic Console bill starts climbing.

**You're now paying Anthropic twice for the same AI.** Every other self-hosted Claude wrapper does this. **datronis-relay is the only one that doesn't.**

| Your setup | Subscription | Typical bot's API overage | **datronis-relay** | You save |
|---|---:|---:|---:|---:|
| 👨‍💻 Solo dev on **Claude Pro** | $20/mo | **+$15/mo** | $20/mo total | **$180 / yr** |
| 👥 Team of 3 on **Claude Teams** | $90/mo | **+$80/mo** | $90/mo total | **$960 / yr** |
| ⚡ Power user on **Claude Max** | $200/mo | **+$120/mo** | $200/mo total | **$1,440 / yr** |

> **One `claude login` command. No API key. No token metering. No overage bills. No key rotation when a teammate leaves. Just your subscription — working in more places.**

---

## 🚀 Install in 5 minutes

```bash
git clone https://github.com/mhmdevan/datronis-relay.git
cd datronis-relay
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .
datronis-relay setup
```

The wizard installs Claude Code, runs `claude login` with a **terminal-side QR code** so the OAuth URL is copy-pastable on a headless server, prompts for your Telegram/Slack tokens, writes `config.yaml`, and installs a hardened systemd unit. Done.

> **Manual install + Docker + systemd recipes:** see [`docs/installation.md`](./docs/installation.md).

---

## ⭐ What you get

- 📱 **Talk to your servers from anywhere.** Telegram + Slack today, Discord next.
- 🌐 **A real admin dashboard** (Next.js 15 + Radix UI) for users, scheduled tasks, adapters, cost, audit log, and live config. **No more SSH + YAML.**
- 🌍 **6 languages out of the box.** English, Deutsch, Español, Français, 中文, 日本語. *(Locked by a key-parity test.)*
- ⏰ **Scheduled recurring tasks.** *"Every morning at 8am, check disk space and ping me if over 80%"* — one chat command, one bot, forever.
- 💰 **Per-user cost tracking + CSV export.** Tokens and USD spend, filtered by today / 7d / 30d / all-time.
- 📊 **Cursor-paginated audit log.** Every message, every Claude call, append-only in SQLite.
- 🛡️ **Hardened for production.** STRIDE threat model, structured JSON logs with correlation IDs, Prometheus metrics, hardened systemd unit, multi-stage Docker, non-root user, read-only rootfs.
- 🧪 **~230 tests.** `mypy --strict`, `ruff`, `eslint`, **zero `any`**, zero warnings, zero flakes.

---

## ⚡ This is happening on your team right now

- 🗝️ Somebody's about to commit `ANTHROPIC_API_KEY=sk-ant-…` to git.
- 💸 Your pay-per-token bot is burning credits on a retry loop you don't know about.
- 📱 Your on-call engineer is SSH-ing from a phone at 2am.
- 🔁 Your teammate left three months ago and nobody rotated their keys.

**[See the full list and the personas →](./docs/use-cases.md)**

---

## 🆚 How it compares

| Feature | Typical Claude chat wrappers | Hubot / Errbot ChatOps | ChatGPT / Claude Teams (SaaS) | **datronis-relay** |
|---|:---:|:---:|:---:|:---:|
| **Pay with your Claude subscription** | ❌ API key only | — | — *(vendor-locked)* | ✅ **`claude login`** (primary) |
| Self-host on your own server | varies | ✅ | ❌ | ✅ |
| Admin web dashboard | ❌ | ❌ | ✅ *(SaaS only)* | ✅ Next.js 15 + 6 locales |
| Multi-user with per-user tool allow-lists | ❌ | limited | ✅ | ✅ + per-user rate limits |
| Scheduled recurring tasks | ❌ | hand-written handlers | ❌ | ✅ `/schedule 1h check disk` |
| Per-user cost tracking in USD | ❌ | ❌ | internal only | ✅ SQLite ledger + CSV |
| Append-only audit log | ❌ | limited | internal only | ✅ SQLite + cursor pagination |
| Clean Architecture + `mypy --strict` | ❌ | ❌ | — | ✅ 4 layers, zero cycles |
| Built-in i18n | ❌ | ❌ | en only | ✅ en / de / es / fr / zh / ja |

> **Every checkmark in the right column is shipped and locked by a test in this repo.** Every ❌ in the other columns is a problem you're already living with — or about to find out you have.

---

## 📚 Documentation

The README is the elevator pitch. Everything else is in **[`docs/`](./docs)** and on the auto-deployed live site (built with mkdocs-material).

| If you want to… | Read |
|---|---|
| 🚀 Get the bot running in 10 minutes | [`docs/quickstart.md`](./docs/quickstart.md) |
| 📦 See every install path (wizard, manual, Docker, systemd) | [`docs/installation.md`](./docs/installation.md) |
| 💬 Set up Slack | [`docs/slack_setup.md`](./docs/slack_setup.md) |
| 🌐 Explore the Next.js admin dashboard | [`docs/web-dashboard.md`](./docs/web-dashboard.md) |
| 🏗️ Understand the architecture (diagrams + tech decisions) | [`docs/architecture.md`](./docs/architecture.md) |
| 🚧 Read the engineering challenges + key achievements | [`docs/engineering.md`](./docs/engineering.md) |
| 🧪 See the testing strategy + quality gates | [`docs/testing.md`](./docs/testing.md) |
| 💡 Find the persona that's you (with full Before/After) | [`docs/use-cases.md`](./docs/use-cases.md) |
| 📊 Read the performance benchmarks | [`docs/performance.md`](./docs/performance.md) |
| 🔒 Review the STRIDE threat model | [`docs/security.md`](./docs/security.md) |
| 📜 Look up the public API surface (SemVer source of truth) | [`docs/api_reference.md`](./docs/api_reference.md) |
| 🏷️ Understand the SemVer + deprecation policy | [`docs/versioning.md`](./docs/versioning.md) |
| 🗺️ Track the roadmap | [`docs/roadmap.md`](./docs/roadmap.md) |
| 📝 Read the changelog | [`docs/changelog.md`](./docs/changelog.md) |

---

## 🔒 Security

**Do not open public issues for security vulnerabilities.** Use the GitHub Private Security Advisory flow or email the maintainer. See [`SECURITY.md`](./SECURITY.md) for the response SLA and [`docs/security.md`](./docs/security.md) for the full STRIDE threat model.

---

## 🤝 Contributing

Contributions are welcome — but this project is opinionated about scope. Open an issue before sending a non-trivial PR so we can agree on the shape. See [`CONTRIBUTING.md`](./CONTRIBUTING.md).

---

## 👤 Author

**Mohammad Eslamnia** — [GitHub](https://github.com/mhmdevan) · Built as a portfolio-grade demonstration of Clean Architecture, multi-platform adapter pattern with contract tests, production observability, and SemVer-committed public API.

---

## 📄 License

MIT — see [`LICENSE`](./LICENSE). Copyright © 2019 Mohammad Eslamnia.

---

<div align="center">

**Built with 🐍 Python, ⚙️ Clean Architecture, and 🤖 Claude Agent SDK.**
*Star ⭐ the repo if it's useful — or fork it and make it yours.*

</div>
