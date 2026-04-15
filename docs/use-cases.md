# Use cases & scenarios

This page collects the operational pain that datronis-relay solves and
the personas it's built for. The README has the short version; this
page has the full set.

## ⚡ Right now, while you're reading this

**Every day you don't have datronis-relay, at least one of these is
happening on your team:**

- 🗝️ **Somebody is about to commit `ANTHROPIC_API_KEY=sk-ant-...` to
  git.** One grep, one leaked key, one compromised org. → *Solved:
  subscription OAuth lives in `~/.claude`, never in env files, never in
  source control, never in a `.env.local` shared on Slack.*
- 💸 **Your pay-per-token chat bot is burning credits on a retry loop
  you don't know about** — you'll see it when the monthly invoice
  arrives. → *Solved: no API key, no per-message billing, no surprise
  overage.*
- 📱 **Your on-call engineer is SSH-ing from a phone at 2am**, typing
  `tail -50` on a 4-inch screen, praying they don't typo `rm`. →
  *Solved: `"explain the last 50 lines on web-1"` via Telegram.*
- 📋 **Your compliance review is about to ask "where's the audit log
  for LLM-driven operations?"** You don't have one. → *Solved: SQLite
  append-only audit log with correlation IDs, cursor pagination,
  filterable by user / event / date range.*
- 🌍 **Your Spanish-speaking junior SRE is pasting your English-only
  admin panel into Google Translate.** → *Solved: 6 locales shipped —
  en / de / es / fr / zh / ja — locked by a key-parity test that fails
  CI if any locale drifts.*
- ✏️ **You're editing `config.yaml` over SSH to add a new user.**
  Again. With no validation. No audit trail. No rollback. → *Solved:
  Next.js 15 admin dashboard with zod-validated forms and a real audit
  log.*
- 🔁 **Your teammate left three months ago and nobody rotated the API
  keys they knew about.** → *Solved: subscription login means there's
  no API key to rotate — ever.*
- ⏰ **That "run every morning at 8am" cron job you never got around to
  writing.** → *Solved: `/schedule 1d check disk` from any chat,
  instantly.*

**Every item on this list is a problem someone on your team has right
now. datronis-relay fixes all of them in one install command.**

---

## 💡 Before / After — pick the one that's you

### 👨‍💻 The solo developer with Claude Pro

**Before:** You pay $20/month for Claude Pro on your laptop. To use
Claude from your phone, you install a self-hosted Telegram bot. It
asks for an API key. You create one in the console and paste it into a
`.env` file. At the end of the month, you realize you spent **$47 on
top** of your Pro subscription. You had a retry-loop bug you didn't
even know about.

**After datronis-relay:** You run `datronis-relay setup`. It installs
Claude Code, runs `claude login`, writes `config.yaml`, and generates a
systemd unit. Coffee in hand, you text *"any new errors in nginx
overnight?"* from bed. The answer arrives before your coffee is done
brewing. **You pay $20. That's it. Forever.**

### 👩‍💼 The DevOps team lead

**Before:** Three engineers, three laptops, three personal Claude API
keys committed to three different `.env.local` files. Compliance hates
you. SSH access to prod is an even bigger liability. When Bob leaves
the team, nobody remembers which keys he knew about or how to rotate
them. Security audit is next week.

**After datronis-relay:** One install. Three user IDs in `config.yaml`,
each with their own `allowed_tools` (Alice: `Read` only; Bob: `Read` +
`Bash`; Carol: full access) and per-user rate limits. Every message
hits a real audit log with correlation IDs. All tokens bill to the
team's **Claude Teams** plan. When Bob leaves, you delete one line and
he's revoked — **no keys to rotate, because there aren't any keys**.

### 📟 The 2am on-call engineer

**Before:** PagerDuty wakes you up. Your laptop is downstairs. You
unlock your phone, squint at tiny terminal fonts, try to type `ssh
prod-web-1` on a phone keyboard. You typo three times. You finally get
in. You grep logs with one thumb while your other hand holds the phone
at the right angle to read. **You're back in bed at 3:45am.**

**After datronis-relay:** You unlock your phone. You open Telegram. You
type *"explain the last 50 log lines on web-1 and tell me if I need to
worry"*. Fifteen seconds later: natural-language summary, root-cause
hypothesis, suggested fix — all in a thread you can scroll with one
thumb from under the covers. **You're back in bed by 2:04am.**

### 🎓 The open-source evaluator

**Before:** You want a real Claude chat-bot reference project for your
architecture review. You search GitHub. You find dozens of weekend-
project wrappers — zero of them hardened, zero with a web UI, zero
with tests that would pass code review at your company, zero with i18n.

**After datronis-relay:** You land on the README. You see `mypy
--strict`, a 4-layer Clean Architecture, `ReplyChannelContract`
subclassed per adapter for free regression coverage, 120+ backend tests
+ 108 UI tests, STRIDE threat model, hardened systemd, multi-stage
Docker, six locales with enforced key-parity. **You bookmark the repo
and link it in your next architecture review as "what good looks
like."**

---

## 🆚 How it compares

| Feature | Typical Claude chat wrappers | Hubot / Errbot-era ChatOps | ChatGPT / Claude Teams (SaaS) | **datronis-relay** |
|---|:---:|:---:|:---:|:---:|
| **Authenticate with your Claude subscription** | ❌ API key only | — | — *(vendor-locked login)* | ✅ **`claude login`** (primary path) |
| Authenticate with an API key (fallback) | ✅ | — | — | ✅ optional fallback |
| Self-host on your own server | varies | ✅ | ❌ | ✅ |
| Admin dashboard (web UI) | ❌ *(CLI or nothing)* | ❌ | ✅ *(SaaS only, vendor-locked)* | ✅ Next.js 15 + Radix, 6 locales |
| Multi-user with per-user tool allow-lists | ❌ | limited | ✅ | ✅ per-user `allowed_tools` + rate limits |
| Scheduled recurring tasks | ❌ | you write handlers by hand | ❌ | ✅ `/schedule 1h check disk` |
| Per-user cost tracking in USD | ❌ | ❌ | internal only | ✅ SQLite ledger + CSV export |
| Structured append-only audit log | ❌ | limited | internal only | ✅ SQLite + cursor pagination |
| LLM-driven (not a hard-coded command dictionary) | ✅ | ❌ | ✅ | ✅ Claude Agent SDK |
| Clean Architecture + SOLID | ❌ | ❌ | — | ✅ 4 layers, zero cycles, `mypy --strict` |
| File / image uploads to Claude | ❌ | ❌ | ✅ | ✅ 10 MB default, per-user cap |
| Built-in i18n (not en-only) | ❌ | ❌ | en only | ✅ en / de / es / fr / zh / ja |
| Production packaging (Docker + hardened systemd) | ❌ | partial | — | ✅ multi-stage, non-root, read-only rootfs |

> **Every checkmark in the right column is already shipped.** Every one
> is locked by a test in this repo. Every ❌ in the other columns is a
> problem you're already living with — or about to find out you have.
