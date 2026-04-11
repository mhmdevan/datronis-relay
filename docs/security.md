# datronis-relay — Security Model & STRIDE Threat Analysis (v0.2.0)

This document captures the Phase 2 threat model. It is a living document: every change that widens the attack surface (new adapter, new backend, new config surface) should add or revise entries here as part of the per-feature Definition of Done.

---

## 1. Assets

Things the system protects, roughly in order of impact.

| # | Asset | Why it matters |
|---|---|---|
| 1 | **Anthropic API key** | Direct financial exposure; rate-limit bypass. |
| 2 | **Telegram bot token** | Remote control of the bot — message every prior conversation partner, impersonate the bot. |
| 3 | **SSH keys / server credentials** (Phase 2.5+) | Full control of downstream servers. Not in v0.2.0 yet. |
| 4 | **SQLite database** (`data/relay.db`) | Audit log, cost ledger, session ids, user allowlist copy. Tampering hides malicious activity. |
| 5 | **Prompt content** (in transit + at rest in audit log) | Trade secrets, credentials pasted by users, internal URLs. |
| 6 | **Correlation ids** | Not sensitive by themselves, but they link logs to sessions — useful to an attacker triaging which request to forge. |

---

## 2. Trust boundaries (Phase 2)

```
┌──────────────────────┐   TLS   ┌─────────────────┐
│ Telegram user's app  │ ──────▶ │ Telegram servers│
└──────────────────────┘          └────────┬────────┘
                                           │ HTTPS long-poll
                                           ▼
                              ┌────────────────────────┐
                              │ datronis-relay process │ ── reads ──▶ config.yaml  (trusted)
                              │  - adapter             │                env vars    (trusted secrets)
                              │  - core                │                SQLite file (trusted)
                              │  - claude_client       │
                              └────────┬───────────────┘
                                       │ HTTPS
                                       ▼
                              ┌────────────────────────┐
                              │  Anthropic API         │
                              └────────────────────────┘
```

**Trusted:** the host OS, the filesystem paths owned by the `datronis` user, the env (secrets), the YAML config.
**Untrusted:** everything Telegram delivers (message content, file attachments, user id), everything the Anthropic API returns.

---

## 3. STRIDE

### S — Spoofing

| Threat | Impact | Mitigations (v0.2.0) | Gaps |
|---|---|---|---|
| Attacker claims to be an allowed user | Unauthorized access to the agent | Auth allowlist keyed on namespaced `telegram:<uid>`; Telegram verifies sender identity end-to-end and we trust their `user_id`. | If the Telegram API is compromised or a malicious bot admin adds our bot to a group, group messages could masquerade. **Action:** in Phase 2.5, refuse all messages from group chats unless explicitly opted in. |
| Attacker registers a bot with the same name | Brand confusion, not a credential compromise | Bot tokens are unique per bot; we bind to a specific token. | None. |

### T — Tampering

| Threat | Impact | Mitigations | Gaps |
|---|---|---|---|
| Modify `config.yaml` on disk to add a rogue user id | Full access to the agent | `config.yaml` is owned by the `datronis` user and readable only by that user (file mode 640 recommended; systemd unit `ReadWritePaths` is restrictive). | No file-integrity monitoring. Add `auditd` or `tripwire` watch on the config path for hardened deployments. |
| Modify the SQLite database to hide audit entries | Repudiation + audit bypass | WAL mode + FK constraints make accidental corruption less likely; backup cadence is the user's responsibility. | No signed audit log. **Action:** Phase 3 — consider append-only remote syslog for critical events. |
| Telegram MITM injects messages | Impersonation | TLS on Telegram's side; long-polling uses HTTPS. | A compromised Telegram CA cert would defeat this; out of scope. |
| Prompt injection inside user messages | LLM produces attacker-desired output | Per-user **tool allowlist** limits which tools Claude can invoke even if persuaded. Rate limiter bounds blast radius. | Classic prompt injection is not fully preventable. **Action:** Phase 2.5 — add confirm-before-write-action for any multi-host command. |

### R — Repudiation

| Threat | Impact | Mitigations | Gaps |
|---|---|---|---|
| User denies sending a command | Legal / incident-response hazard | Every message → `audit_log` row with `correlation_id`, `user_id`, `ts`, tool invoked, exit code. | Audit log is local-only; a compromised host can be tampered with offline. **Action:** optionally ship audit entries to a remote sink. |
| Claude SDK response lost without trace | Cannot correlate cost or tool usage | `CompletionEvent` usage totals are persisted via `CostTracker`; structured logs carry correlation ids. | If the process crashes mid-stream, the completion event is never emitted — cost for that request is lost. Acceptable for Phase 2; consider a watchdog timer in 2.5. |

### I — Information Disclosure

| Threat | Impact | Mitigations | Gaps |
|---|---|---|---|
| Secrets logged accidentally | Credential leak | `SecretStr` type in pydantic config; no secrets in error messages; `_safe_send` error path uses a category + correlation id only. | No CI redaction test yet — add a pytest that greps for common secret patterns in captured logs. |
| Audit log exposes user prompts | Privacy concern | `audit_log.command` and `audit_log.tool` may store prompt content; documented in the STRIDE notes; user is warned in `docs/quickstart.md`. | v0.2.0 does not redact PII from prompts. **Action:** Phase 3 — optional hashing of `command` at rest. |
| Cost summary discloses usage patterns | Minor | `/cost` is per-user only; no cross-user enumeration is possible because the command reads only for the authenticated user id. | None. |
| `config.yaml` readable by other users | Full compromise | Recommend file mode 640, owner `datronis`. | We don't verify permissions on startup. **Action:** warn at startup if `stat` shows world-readable. |

### D — Denial of Service

| Threat | Impact | Mitigations | Gaps |
|---|---|---|---|
| Allowed user floods the bot with prompts | Cost runaway, queue backup | Per-user **rate limiter** (minute + day buckets) from `RateLimiter`. | Day bucket is in-memory — restart resets it. Acceptable for v0.2.0; Phase 2.5 can persist. |
| Attacker sends a huge message | Memory pressure | Telegram caps message size; Claude SDK has its own cap. | No explicit max prompt length in our code — add a 32KB cap at the adapter in Phase 2.5. |
| Attacker triggers slow Claude calls repeatedly | Anthropic bill explosion | Daily token cap via the pricing model + rate limiter; cost tracker exposes `/cost` for the user to self-monitor. | No hard-stop daily USD cap. **Action:** Phase 2.5 — add `per_user_daily_cost_cap_usd` to config. |
| Claude SDK hangs | Worker pool starvation | `claude-agent-sdk` calls run inside an asyncio Task; `/stop` can reset but does not currently cancel an in-flight SDK call. | **Action:** Phase 2.5 — track the in-flight task per user and make `/stop` cancel it. |
| SQLite exhausts disk | Process crash | WAL file size is bounded; audit log grows unboundedly. | **Action:** Phase 3 — add a retention job that prunes `audit_log` rows older than N days. |

### E — Elevation of Privilege

| Threat | Impact | Mitigations | Gaps |
|---|---|---|---|
| Allowed user tricks Claude into running a tool they're not authorized for | Executes beyond their blast radius | **Tool allowlist** per user in YAML → forwarded to `ClaudeAgentOptions.allowed_tools`. SDK enforces. | We only pass the allowlist; we don't verify the SDK honors it in every version. **Action:** pin a known-good SDK version and add an integration test that passes an empty allowlist and asserts no tool was called. |
| Bot process gains extra privileges | Host compromise | systemd unit uses `NoNewPrivileges`, `ProtectSystem=strict`, `CapabilityBoundingSet=`, `MemoryDenyWriteExecute`, `ProtectHome`, etc. Docker: `read_only: true`, `no-new-privileges: true`. | User running via `pipx` has no sandbox. **Action:** document that self-host users should run under a dedicated low-privilege account. |
| Secrets vault key leak (Phase 2.5) | Full server compromise | Not applicable in v0.2.0 — no vault yet. | Will be the #1 concern in Phase 2.5. |

---

## 4. Non-STRIDE concerns

- **Backup strategy.** `data/relay.db` is your audit + cost ledger. Document a backup + restore runbook before any production use. Suggested: `sqlite3 data/relay.db ".backup data/backup-$(date +%F).db"` via cron.
- **Key rotation.** Rotate `ANTHROPIC_API_KEY` every 90 days. Rotating the Telegram bot token requires a restart; document it.
- **Dependency updates.** Dependabot / Renovate should open PRs weekly. High/critical CVEs block other work per roadmap §7.4 alarm thresholds.
- **Supply chain.** Pin the `claude-agent-sdk` version in `pyproject.toml` and verify the hash before upgrading. The SDK is the highest-risk dependency because it directly holds an API key with financial exposure.

---

## 5. Open questions for Phase 2.5

1. Should the rate limiter's daily bucket be persisted in SQLite so it survives restarts?
2. Do we ship a signed append-only audit log for regulated environments?
3. Should `/stop` also abort the in-flight Claude stream, not just reset the session?
4. When voice arrives, what's the audio retention policy by default — delete immediately, or keep for a configurable window?

These are tracked as bullet points and will be resolved before the Phase 2.5 security checklist sign-off.

---

**Last reviewed:** 2026-04-11.
**Next review due:** before tagging v0.2.5.
