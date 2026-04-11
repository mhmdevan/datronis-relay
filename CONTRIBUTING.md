# Contributing

Thanks for your interest in contributing. This project takes a small number of changes per week, reviewed carefully — we optimize for a stable, easy-to-reason-about codebase over fast turnaround on features. If you're planning a non-trivial change, please open an issue first so we can agree on the shape.

## Quick start

```bash
git clone https://github.com/mhmdevan/datronis-relay.git
cd datronis-relay
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# fast feedback loop
pytest -m "not integration"
mypy src
ruff check .

# full run
pytest
```

All four commands must be green before a PR can land.

## Project layout

Clean Architecture. Dependency direction is strictly one-way: **adapters → core → domain**, and **infrastructure → core** (infrastructure implements the ports the core depends on). Adapters never import core's internal types directly; they talk only to `MessagePipeline` + `ReplyChannel`.

```
src/datronis_relay/
├── domain/          # pure dataclasses and enums. No side effects.
├── core/            # platform-agnostic use cases + ports (protocols).
├── infrastructure/  # concrete port implementations (SQLite, Claude SDK, metrics, config).
└── adapters/        # platform-specific I/O (Telegram, Slack).
```

**When in doubt, put new code one layer further out than you think you should.** A Telegram-specific constant does not belong in `core/`, even if it's tempting. A SQLite query does not belong in `domain/`.

## Coding standards

- **Python 3.11+**, `mypy --strict`, `ruff check .` with the rules configured in `pyproject.toml`.
- Prefer **frozen dataclasses** for value objects.
- Use **Protocols** (`typing.Protocol`) for ports.
- Every public function has a docstring explaining the _why_, not the _what_.
- Tests are required for every new use case. New ports require contract tests.
- No broad `except Exception:` without logging + a comment explaining why.
- No `print`. Use `structlog.get_logger(__name__)`.
- Async everywhere. No `threading` in user code.

## Tests

We run three categories:

- **Unit** (`tests/unit/`) — fast, in-memory, no network.
- **Integration** (`tests/integration/`, marker `integration`) — real SQLite, real `MessagePipeline`, fake adapters.
- **Contract** (`tests/unit/test_reply_channels.py`) — a single abstract suite subclassed by every `ReplyChannel` implementation. Adding a new adapter means adding one subclass here.

Coverage target: **≥ 80%** for changed files (enforced via `coverage.report.fail_under` in `pyproject.toml`).

## Commit messages

Conventional-ish. The format we use:

```
feat(scheduler): respect per-user tool allowlist on scheduled tasks

Why: a scheduled task that bypasses the allowlist would let a locked-down
user do things their realtime chat is blocked from. The scheduler already
uses MessagePipeline so this is a 3-line change.
```

Prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

## Pull requests

- One logical change per PR. Multiple unrelated fixes → multiple PRs.
- PR description should answer:
  1. What problem does this solve?
  2. How does it solve it?
  3. What alternatives were considered?
  4. What's _not_ covered by this PR?
- Link any related issue.
- CI must pass (lint, type, test, build).
- Update `docs/changelog.md` under the `## [Unreleased]` section if the change is user-visible.
- Update `docs/api_reference.md` if the public surface changes.

## What counts as a breaking change

From v1.0.0 onward, **breaking changes require a major version bump**. A breaking change is any of:

- Removing or renaming a public symbol listed in `docs/api_reference.md`.
- Changing a public function's signature in a way that existing callers would fail.
- Changing the YAML config schema in a way that breaks existing files.
- Changing the SQLite schema without a migration.
- Removing a command that users depend on.

Everything else is non-breaking and lands in a minor or patch.

## Deprecation policy

When we do need to break something:

1. Mark the symbol as deprecated in the next minor release. Add a `DeprecationWarning` at call time and a note in `docs/changelog.md`.
2. Maintain the deprecated behavior for at least **one full minor cycle**.
3. Remove in the next major.

See `docs/versioning.md` for the full contract.

## Security

Do **not** open public issues for security vulnerabilities. See [`SECURITY.md`](./SECURITY.md) for the private reporting process.

## Code of conduct

See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md). TL;DR: be kind, assume good faith, disagree with the argument not the person.
