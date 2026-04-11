# Versioning & Deprecation Policy

datronis-relay follows [Semantic Versioning 2.0.0](https://semver.org/) **from v1.0.0 onward**. Pre-1.0 releases (0.1.x through 0.4.x) were explicitly marked in the roadmap as allowed to break between minors — that caveat no longer applies.

This page is the contract. If the code or the changelog contradicts it, the contract wins and the code is a bug.

## The short version

- **`1.0.x`** — bug fixes only. Drop-in replacements. No new features, no config-schema changes, no signature changes.
- **`1.x.0`** — additive changes. New features, new config fields (with defaults), new adapters, new optional parameters. Existing public symbols keep working.
- **`2.0.0`** — removals or renames. Requires a one-minor-cycle deprecation window and a migration guide in the changelog.

## What "public" means

The definition of "public" is [`api_reference.md`](./api_reference.md). Anything listed there is stable. Anything not listed is internal — it may change in any release, for any reason, without notice.

If you're relying on an internal symbol, **open a discussion**. We're usually happy to promote something to public if there's a real use case.

## What counts as a breaking change

From v1.0.0 onward, **any** of the following requires a major version bump:

| Change | Why it's breaking |
|---|---|
| Removing a public symbol | Existing imports fail |
| Renaming a public symbol | Same as removal |
| Removing a positional parameter from a public function/constructor | Existing calls fail |
| Adding a *required* parameter to a public function/constructor | Existing calls fail |
| Changing the return type in a way incompatible with existing consumers | Runtime failures |
| Removing an enum variant from a public enum | Existing pattern matches fail |
| Removing a field from a public dataclass | Existing consumers break |
| Renaming a YAML config key | Existing `config.yaml` files fail to load |
| Changing a SQLite schema in a way that a migration can't auto-apply | Existing databases fail on startup |
| Removing a chat command | Muscle memory breaks, scheduled tasks that reference it fail |

## What is NOT a breaking change

These are explicitly non-breaking and may land in a minor:

- Adding a new public symbol.
- Adding a new optional parameter (with a default) to a public function.
- Adding a new field (with a default) to a public dataclass.
- Adding a new variant to an enum — **consumers must handle the default case in match statements**, which is the Python norm.
- Adding a new method to a `Protocol` that the core doesn't call. (Protocols are structural; if the core doesn't require the new method, existing implementations keep working.)
- Adding a new adapter or a new store implementation.
- Fixing a bug — even one that existing code was accidentally relying on. Bug fixes are not breaking changes, and "my code broke because the bug went away" is not a SemVer violation.
- Changing error messages. The `ErrorCategory` enum is stable; the human-readable `str` is not.
- Changing log line shapes. Logs are operator-facing, not API.
- Changing the Prometheus metric *values* (the counters themselves are labels-stable).

## Deprecation process

When we need to break something, the process is:

### 1. Deprecate in version `1.n.0`

- Add a `DeprecationWarning` at call time with a message pointing at the replacement.
- Add an entry to `docs/changelog.md` under `### Deprecated`.
- Do **not** remove or change the behavior of the deprecated symbol — it must keep working exactly as before.

### 2. Maintain through `1.n.0` → `1.(n+1).*`

- The deprecated symbol must keep working through at least one full minor cycle.
- If a critical security issue forces an immediate removal, that becomes its own major release — we don't let "security" override the deprecation contract silently.

### 3. Remove in `2.0.0`

- The symbol goes away in the next major bump.
- The migration guide in the changelog must explicitly list every removed symbol and its replacement.

### Example

```
v1.3.0  — add the new method. Deprecate the old one.
v1.4.0  — still supported. Warning is still emitted.
v2.0.0  — old method removed. Changelog has a migration table.
```

A three-release minimum is the floor. More is fine; less is not.

## Pre-1.0 releases

The 0.x line is frozen. It received no fixes after the 1.0.0 release. If you're running 0.x, the only supported migration path is forward to 1.0.0, and the [changelog](./changelog.md) has per-version migration guides for every step in the chain.

## Security releases

A critical security fix may be released as a patch to the current minor **and** backported to the previous minor if it's within 30 days of the previous minor's release. We do not maintain LTS branches — the expectation is that users stay within one minor of `main`.

## "What about my third-party adapter?"

If you've written a Discord or WhatsApp adapter on top of `ChatAdapterProtocol`:

- Your adapter will continue to work as long as it implements the protocol correctly.
- If a new method is added to `ChatAdapterProtocol` in a minor, the core will only call it when your adapter provides it (structural typing + `hasattr` dispatch).
- If the new method is **required** to use a new feature, it lands in the *next* major — not in a minor.

In practice, the only hard requirement for an adapter class in v1.x is `async def run_forever(self) -> None` and `def build_reply_channel(self, channel_ref: str) -> ReplyChannel`. Everything else is fair game for additive evolution.

## SemVer FAQ

**Q: You added a new optional parameter with a default. My test fails because I was calling the function with keyword arguments only, and my linter doesn't like the new one. Is that a breaking change?**
A: No. That's a linter problem. SemVer governs runtime compatibility, not static tooling.

**Q: You changed a log line and my log-scraper broke.**
A: Logs are not API. Use the Prometheus metrics or the audit log for machine-readable state.

**Q: You fixed a bug that my code was accidentally relying on.**
A: Not a breaking change. Your code was relying on incorrect behavior, which by definition is a bug. The fix lands in a patch or minor depending on other changes in the same release.

**Q: You added a new enum variant and my `match user.platform:` statement is now exhaustive-checked wrong.**
A: Python doesn't enforce exhaustive matching, so runtime behavior is unchanged. Your static analyzer (mypy) may warn — add a catch-all arm. We are explicit in the docs that new variants may be added.
