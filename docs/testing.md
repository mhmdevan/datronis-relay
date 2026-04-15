# Testing strategy

**Five test categories** — four on the Python backend, one on the
Next.js UI. The total is **120+ backend cases + 108 UI cases ≈ 230
tests**, all passing, no flakes.

## Backend (pytest)

| Category | Location | What it tests | How |
|---|---|---|---|
| **Unit** | `tests/unit/` | Every core module in isolation | Fakes injected at Protocol boundaries |
| **Integration** | `tests/integration/` (marker: `integration`) | Full pipeline + real SQLite | Temp-dir database per test, real `MessagePipeline` |
| **Contract** | `tests/unit/test_reply_channels.py` | Every `ReplyChannel` impl | Abstract `ReplyChannelContract` subclassed per adapter — new adapters get free regression coverage |
| **Load / concurrency** | `tests/integration/test_load.py` | Pipeline under 100 concurrent users | `asyncio.gather`, asserts wall time + rate-limit correctness |

## Frontend (vitest, 108 tests / 10 files)

| Category | Location | What it tests | How |
|---|---|---|---|
| **Schema validation** | `ui/tests/unit/{user,task,adapter,config,cost,audit,csv}-schemas.test.ts` | Every zod schema powering a form or API response | Pure `safeParse` assertions — error messages are i18n *keys* so tests stay stable across translation edits |
| **Pure helpers** | `ui/tests/unit/{interval,csv}.test.ts` | Preset round-trip, CSV escape rules, numeric sort | Node-env only, no DOM, no Radix imports |
| **Locale parity** | `ui/tests/unit/locale-parity.test.ts` | Every non-English locale has the same key tree as `en.json` | Walks JSON, diffs key sets — fails CI if a translator misses a new key |
| **RTL infrastructure** | `ui/tests/unit/is-rtl.test.ts` | `isRtl()` returns false for active locales, true for `ar`/`he` | Locks the infrastructure contract before any future RTL locale lands |

## Key testing principles

- **Fakes at ports, not patches of libraries** — `FakeClaude` implements
  `ClaudeClientProtocol`; `FakeCostStore` implements `CostStoreProtocol`;
  `FakeScheduledStore` implements `ScheduledTaskStoreProtocol`. No
  `unittest.mock.patch` on `telegram.` or `slack_sdk.`.
- **Real SQLite for integration tests** — each test gets a fresh
  temp-dir database, migrations run, cleanup happens via the `tmp_path`
  fixture. Mocked DBs were explicitly rejected during the Phase 2
  hardening review (see `changelog.md`).
- **Contract tests** — the Phase 3 `ReplyChannelContract` forces every
  `ReplyChannel` implementation (Telegram, Slack, any future Discord) to
  pass the same abstract test suite. Adding a new adapter is a one-line
  subclass.
- **Concurrency tests** — `test_session_store_is_concurrency_safe`,
  `test_concurrent_callers_are_serialized`,
  `test_one_hundred_concurrent_asks_complete` — the invariants that
  would be invisible in single-threaded tests are pinned.
- **No broken-window exceptions** — tests that pass "most of the time"
  are quarantined and fixed, not `@pytest.mark.flaky`-ed.

## Quality gates (enforced in CI)

### Backend

```bash
ruff check .          # lint — 0 errors required
ruff format --check . # formatting — 0 errors required
mypy src              # --strict — 0 errors required
pytest                # full suite — all green required
```

### Frontend (run inside `ui/`)

```bash
pnpm lint             # eslint flat config + next/typescript — 0 warnings required
pnpm typecheck        # tsc --noEmit — 0 errors required
pnpm test             # vitest run — 108 tests all green
pnpm build            # production bundle — every route under 250 KB first-load JS
```

Backend coverage target **≥ 80 %** enforced via
`coverage.report.fail_under = 80` in `pyproject.toml`. Frontend KPIs
(locale parity, bundle budget, zero `any`, zero ESLint warnings) are
locked by the tests and the build itself.
