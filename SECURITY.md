# Security Policy

datronis-relay is a chat-ops bridge with direct access to a Claude API key and, in the future, SSH keys and server credentials. Security reports are treated as the highest priority of any work in this repository.

## Supported versions

From v1.0.0 onward, the latest minor on `main` is supported. Older majors receive no fixes; users must upgrade.

| Version | Supported |
|---|---|
| 1.0.x   | ✅ |
| < 1.0   | ❌ (pre-1.0 releases were explicitly marked as unstable; upgrade) |

## Reporting a vulnerability

**Do not open a public GitHub issue for a security vulnerability.**

Instead, please use one of the following private channels:

1. **GitHub Private Vulnerability Reporting** — the preferred channel.
   Open [`Security → Advisories → Report a vulnerability`](https://github.com/datronis/datronis-relay/security/advisories/new) on the repository.

2. **Email** — a maintainer-monitored address. See the `README.md` or the [`pyproject.toml`](./pyproject.toml) `authors` field for contact information.

Please include:

- A description of the vulnerability and the conditions that trigger it.
- The version you were running (`datronis-relay --version` or check `pyproject.toml`).
- Steps to reproduce, if possible.
- The impact you believe the vulnerability has.

## Response SLA

| Severity | Initial response | Patch target |
|---|---|---|
| Critical (remote command execution, auth bypass, credential leak) | < 24 hours | < 7 days |
| High (e.g., DoS, privilege escalation in the tool allowlist) | < 48 hours | < 30 days |
| Medium / Low | < 7 days | next scheduled minor |

We follow **responsible disclosure**: please give us a reasonable window to ship a fix before discussing the vulnerability publicly. We will credit reporters in the release notes unless you ask to stay anonymous.

## Scope

In scope:

- The code in `src/datronis_relay/`.
- The default configuration shipped in `config.example.yaml` and `.env.example`.
- The systemd unit and Dockerfile in `examples/` and the repository root.
- The CI/CD workflows in `.github/workflows/`.

Out of scope:

- Vulnerabilities in upstream dependencies (report those upstream). We do track them via `dependabot` / renovate and will ship patches once upstream fixes are released.
- User configuration mistakes (e.g., committing `config.yaml` with a bot token to a public repo) — though we're happy to improve docs if a config surface is easy to misuse.
- Anything caused by running an unsupported version.

## Threat model and security architecture

The in-depth threat model is in [`docs/security.md`](./docs/security.md) — a STRIDE analysis with per-threat mitigations and a **Gaps** column for what's not yet covered. Reviewers should start there.

## Hardening checklist for self-hosters

- Put secrets in env vars (`DATRONIS_TELEGRAM_BOT_TOKEN`, `DATRONIS_SLACK_*`, `ANTHROPIC_API_KEY`), not in `config.yaml`.
- Run under a dedicated non-login user account (see `examples/systemd/datronis-relay.service` for a hardened unit with `NoNewPrivileges`, `ProtectSystem=strict`, `MemoryDenyWriteExecute`).
- Use `allowed_tools: []` only for trusted users — every other user should have an explicit tool allowlist.
- Keep `attachments.max_bytes_per_file` conservative; the default is 10 MB.
- Back up `data/relay.db` regularly (the audit log and cost ledger live there).
- Rotate your `ANTHROPIC_API_KEY` at least every 90 days.
