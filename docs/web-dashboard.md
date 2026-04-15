# Web dashboard

Not every operator wants to edit `config.yaml` over SSH. `datronis-relay`
ships with a **Next.js 15 admin dashboard** (in `ui/`) that reads and
writes the same SQLite database and `config.yaml` the bot uses — no
parallel data store, no duplicated business rules.

**Positioning:** *"The admin panel datronis-relay deserves."*

## Pages (Phases UI-0 → UI-4 — complete)

| Page | What it does | Phase |
|---|---|---|
| **Login** | Password-gated entry with localStorage bearer token | UI-0 |
| **Dashboard** | System status, adapter health, cost-today/7d/30d, recent activity, quick actions | UI-1 |
| **Users** | Full CRUD: add / edit / delete with platform badges, allowed-tools chips, rate-limit fields, toast feedback | UI-1 |
| **Scheduled Tasks** | List, create, pause/resume, delete. Create dialog with a user dropdown + preset interval picker (30s … 1d + custom) | UI-2 |
| **Adapters** | Telegram + Slack cards with enable/disable Radix Switch, status dot (healthy/idle/error), token-rotation dialog. Optimistic-update with revert-on-error | UI-2 |
| **Cost Explorer** | 4 summary cards, daily-cost bar chart (recharts, lazy-loaded), sortable per-user table, date-range selector, client-side CSV export | UI-3 |
| **Audit Log** | Filterable table (event type, user, date range) with cursor-based pagination, expandable rows for per-event details, colour-coded event badges | UI-3 |
| **Settings** | Config form for Claude (model, max turns), Scheduler (enabled, poll interval, max tasks), Metrics (host/port), Attachments (max file size), Logging (level, JSON). Dirty tracking, amber "unsaved changes" banner, restart-bot AlertDialog | UI-4 |

## Four-state UX, everywhere

Every data-fetching page handles **loading / error / empty / success**
explicitly — skeletons that mirror the final layout shape (zero CLS),
retry-able error banners, empty states with CTAs, toasts on every
mutation. The same `useApi` hook drives all of them (AbortController
cancellation on unmount, stale-while-revalidate).

## Internationalization (6 locales)

- 🇬🇧 English (default)
- 🇩🇪 Deutsch
- 🇪🇸 Español
- 🇫🇷 Français
- 🇨🇳 中文 (Simplified)
- 🇯🇵 日本語

Every key is present in every locale — enforced by a **parity test**
(`tests/unit/locale-parity.test.ts`) that walks each JSON and fails CI
if a key is missing or extra. RTL infrastructure (`isRtl()`,
`RTL_LOCALES`, `<html dir>` switching, `rtl:rotate-180` directional
icons) is in place so adding `ar` or `he` is a one-line routing change.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Framework | **Next.js 15 App Router** | React 19 Server Components, co-located API rewrites, file-system routing |
| UI primitives | **Radix UI Themes** | Accessible, composable, WAI-ARIA built-in, dark/light via `<Theme appearance>` |
| Styling | **Tailwind CSS 4** | Logical properties (`ps-`, `pe-`) for future RTL |
| i18n | **next-intl 4** | ICU messages, SSR-safe, lazy-loaded locale bundles (6 locales) |
| Forms | **react-hook-form + zod** | Declarative validation, schema-driven error messages as i18n keys |
| Charts | **recharts** | Lazy-loaded via `next/dynamic({ ssr: false })` to keep cost page under the 250 KB budget |
| Data fetching | Custom **`useApi` hook** | Minimal SWR-style + AbortController — no React Query needed for config CRUD |
| Package manager | **pnpm** | Fast, strict, disk-efficient |
| Testing | **Vitest** (node env) | Pure-logic unit tests; all 108 run in under 650 ms |

## Bundle budget (every page under 250 KB first-load JS)

```
/[locale]                    164 KB   ← dashboard
/[locale]/adapters           206 KB
/[locale]/audit              200 KB
/[locale]/cost               205 KB   ← recharts lazy-loaded (saved 113 KB)
/[locale]/settings           218 KB
/[locale]/tasks              223 KB
/[locale]/users              225 KB
/[locale]/users/[id]         218 KB
/[locale]/login              135 KB
```

## Tests (all Vitest, all pure logic)

| File | Tests | Coverage |
|---|---|---|
| `locale-parity.test.ts` | 5 | Every non-English locale has the same key tree as `en.json` (de / es / fr / zh / ja) |
| `is-rtl.test.ts` | 6 | `isRtl` returns false for active locales, true for `ar` / `he`, case-sensitive |
| `user-form-schema.test.ts` | 9 | UI-1 user form validation + `splitUserId` |
| `task-form-schema.test.ts` | 10 | UI-2 task form validation + `toTaskPayload` platform derivation |
| `adapter-schemas.test.ts` | 8 | UI-2 adapter update + token rotation |
| `interval.test.ts` | 10 | UI-2 interval preset round-trip + custom seconds formatter |
| `cost-schemas.test.ts` | 14 | UI-3 per-user cost schema + `sortCostRows` (numeric, not lexicographic) |
| `audit-schemas.test.ts` | 15 | UI-3 audit event types + `buildQuery` (null vs empty-string skip rules) |
| `csv.test.ts` | 7 | UI-3 CSV escape (comma, quote, newline, format override) |
| `config-schema.test.ts` | **24** | UI-4 every config section + aggregate + multi-section error collection |
| **Total** | **108** | All passing, no flakes |

## Running the dashboard

```bash
cd ui
pnpm install
pnpm dev          # http://localhost:3210 (proxies /api/* to localhost:3100)
pnpm test         # 108 unit tests
pnpm typecheck    # tsc --noEmit, zero errors
pnpm lint         # eslint flat config + next/typescript, zero warnings
pnpm build        # production bundle, every route under 250 KB
```

The dev server runs on **port 3210** (not the conventional 3000) to
avoid clashing with whatever else you might have running locally.
The Next.js rewrite forwards `/api/*` to `http://localhost:3100`,
which is where the Python REST API will live in Phase UI-5.

> **Backend API status:** Phase UI-5 (the Python REST endpoints —
> `/api/users`, `/api/tasks`, `/api/adapters`, `/api/cost/*`,
> `/api/audit`, `/api/config`, `/api/restart`) is the next planned
> phase. The UI is fully wired against these paths with zod-validated
> response parsing; enabling them is a one-sided Python change with
> zero UI work.
