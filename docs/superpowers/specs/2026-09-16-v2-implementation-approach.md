# V2.0 — Recommended Implementation Approach, Tools, and Packages

Date: 2026-09-16
Status: Draft for user review
Companion to `2026-09-16-v2-design.md`. That document says *what*; this one
says *how*: workflow, order of work, packages, module layout per phase, test
strategy, and the traps already learned in v1.

## 1. Guiding principles

Keep the v1 rules that made it ship cleanly; V2.0 adds nothing that needs
new architecture.

- **Service layer owns writes.** Routers stay thin. The audit export, the
  report builder, and the locale patch are all service functions with
  pydantic DTOs out.
- **Engine-neutral schema.** Migration `0002` uses only column types that
  behave identically on SQLite and PostgreSQL. The CI job that applies and
  reverts migrations on PostgreSQL stays the gate.
- **Types flow from the backend.** Every new DTO is regenerated into
  `frontend/src/lib/api/schema.d.ts` with `npm run gen:api`; never hand-type
  one.
- **Pure functions first.** As-of reconstruction, period bounds, the audit
  summary renderer, and label lookup are plain functions with no I/O, so
  they get exhaustive unit tests and the endpoints get thin API tests.
- **No new runtime services.** No jobs loop, no email, no Redis. The
  container stays one process; a v1 `.env` boots V2.0.
- **Small files.** 200–400 lines per module, 800 max; split by feature.

## 2. Workflow

The v1 workflow (spec → per-phase plan → task-by-task execution with TDD →
PR → CI → merge) worked; repeat it.

1. **Plan per phase.** Write
   `docs/superpowers/plans/2026-MM-DD-v2-phase<N>-<name>.md` with the
   `writing-plans` skill: goal, architecture, file structure, and numbered
   tasks with checkboxes, each task being RED → GREEN → run the stated
   command → commit. Plans are reviewed before code starts.
2. **Branch per phase** off `main`: `v2/phase1-audit-log`,
   `v2/phase2-reports`, `v2/phase3-bilingual`, `v2/phase4-release`. One PR
   per phase, squash-merged. Never stack a phase on an unmerged branch; if
   phase N is in review, phase N+1 branches from `main` and rebases later.
3. **Dev log per phase** at `docs/superpowers/logs/…-v2-phase<N>-dev-log.md`
   recording deviations and fixes, as v1 did. Future plans read the previous
   log first.
4. **Cadence inside a phase:** backend task (model → service → schema →
   router → tests) before its frontend task (hook → components → page →
   tests), because the frontend types are generated from the backend.
5. **Definition of done for a task:** tests green locally with the exact
   commands in §7, lint and format clean, one commit, checkbox ticked.
6. **Definition of done for a phase:** CI green (backend ≥ 80% coverage,
   frontend lint/typecheck/test/build, PostgreSQL migrations job, container
   smoke, e2e), dev log written, PR merged, pre-release tag
   (`v2.0.0-alpha.1`, `-alpha.2`, `-beta.1`, then `v2.0.0`). The existing
   `release.yml` publishes the image on every `v*` tag, so each phase can be
   deployed to a staging container for the teams to try.

Agentic execution: each plan carries the v1 header (`REQUIRED SUB-SKILL:
superpowers:subagent-driven-development or superpowers:executing-plans`) so
one worker per task can run with review checkpoints between tasks.

## 3. Order of work and why

```
Phase 1  Audit log ──┐
                     ├──► Phase 3  Bilingual ──► Phase 4  Release
Phase 2  Reports  ───┘
```

- Phase 1 first: smallest, delivers the admin request, and introduces the
  client-side change-summary renderer that Phase 3 needs.
- Phase 2 next: independent of Phase 1 except that its `Change log` sheet
  reuses the Phase 1 audit export writer. It can start in parallel on a
  second branch once Phase 1's exporter refactor has merged.
- Phase 3 last: it touches every screen; doing it after the two new pages
  exist means the strings are extracted once, not twice.
- Phase 4: e2e, coverage gate, docs, Chinese review, tag.

## 4. Packages

### Backend (no new runtime dependencies)

| Need | Use | Why not something new |
|---|---|---|
| Audit and report workbooks | `openpyxl` (already present) | Same writer style as the v1 exporter; keeps one xlsx code path. |
| Period bounds (month / quarter) | stdlib `datetime` + `calendar.monthrange` | Quarter math is three lines; no `dateutil`. |
| As-of reconstruction | plain Python over lists | Event volumes are thousands, not millions; one query per report, computed in memory. |
| Locale-aware export labels | `app/i18n/labels.py` dict per locale | Backend renders no UI; only status / priority / owner / kind / field labels for xlsx. No Babel or gettext. |
| Sign-in events | existing `record_event` | New action strings only. |
| Tests | `pytest`, `pytest-cov`, `httpx` (present) | Inject `today` into pure functions instead of adding `freezegun`. |

Optional dev-only addition: `hypothesis` for one property test that the
as-of reconstruction of "now" equals the current item state for any random
history. Worth it if the scripted tests feel thin; skip otherwise.

### Frontend

| Need | Package | Notes |
|---|---|---|
| Translation runtime | `i18next`, `react-i18next` | The de-facto React choice; JSON bundles; `useTranslation()` hook; namespaces map onto `features/`. |
| Language detection | `i18next-browser-languagedetector` | First-visit default from `navigator.language`; the persisted `user.locale` overrides it after login. |
| Literal-string guard | `eslint-plugin-i18next` (rule `no-literal-string`) | Added to the existing ESLint 9 flat config, scoped to JSX text and `title`/`placeholder`/`aria-label` attributes, `warn` in Phase 3 then `error` in Phase 4. |
| Coverage gate | `@vitest/coverage-v8` | `coverage.thresholds.lines = 70` in `vitest.config.ts`; CI runs `npm test -- --coverage`. |
| Date and number formatting | `Intl` (built in) | `format.ts` already uses it; pass the active locale. No `date-fns` or `dayjs`. |
| Tables, filters, period picker, printable page | hand-rolled, as v1 | The items table is hand-rolled and fine at this size; `<input type="date">` for custom ranges; `@media print` CSS for the printable page. No table, chart, or PDF library. |
| Fonts | CSS only | Extend the Tailwind `font-sans` stack with `"PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC"` and set `<html lang>` from the active locale so CJK glyphs render correctly on all three desktop platforms. |

Nothing else changes: React 19, Vite 6, Tailwind v4, TanStack Query v5,
react-router v7, react-hook-form + zod, Radix, lucide, Vitest 3, Playwright.

## 5. Phase-by-phase implementation notes

### Phase 1 — Audit log

**Backend**

- `services/audit.py`: extend `list_activity` with `until`, `action`,
  `entity_id`, `q` (ILIKE on `summary` and on `changes` cast to text), and
  `include_security` (default false, excludes the three sign-in actions).
  Add `resolve_entity_labels(db, events) -> dict[(type, id), str]` that runs
  one `IN` query per entity type present on the page.
- `schemas/audit.py`: `AuditEventOut.entity_label: str | None`.
- `services/auth.py`: record `signed_in` on success, `sign_in_failed` on a
  wrong password for an existing active user (actor = that user; the
  `actor_id` column is non-null, so unknown emails are only logged, not
  audited), `signed_out` on logout. Keep these out of the dashboard feed by
  passing `include_security=False` from `build_summary`.
- `exporters/audit.py`: `build_audit_export(rows, *, locale) -> bytes`, one
  row per changed field, capped by `AUDIT_EXPORT_ROW_LIMIT`.
- `api/activity.py`: new query params; `GET /activity/export` with `AdminUser`.
- Migration `0002a` (or fold into `0002` if Phase 3 lands first): the two
  indexes. Indexes are additive and engine-neutral.
- Tests: `tests/unit/test_audit_service.py` (filters, label resolution,
  security exclusion), `tests/api/test_activity_api.py` (each filter, admin
  gate on export, row cap), `tests/unit/test_audit_export.py` (one row per
  field, label rendering).

**Frontend**

- `features/admin/audit/`: `audit-filters.ts` (URL ↔ filter object, copy
  the `features/items/filters.ts` pattern and its tests), `useAuditLog.ts`
  (TanStack Query, key `qk.audit(filters)`), `AuditFilterBar.tsx`,
  `AuditTable.tsx` (expandable rows reusing `components/domain/DiffTable`),
  `AuditPage.tsx`, `AuditExportButton.tsx`.
- `lib/audit-summary.ts`: `summarize(event, labels) -> string` builds the
  line from `action` + `changes`. Pure, unit-tested against the fixtures
  that produce the backend `summary`. `HistoryTab` and the dashboard feed
  switch to it now (English), so Phase 3 only swaps the label source.
- `lib/download.ts`: generalize `downloadExport` to `downloadFile(path,
  params)`.
- Router: `/admin/audit` under `AdminRoute`; `AdminLayout` tab. Users page:
  "View activity" link to `/admin/audit?actor_id=…`.
- Tests: filter parsing, summary renderer, `AuditTable` rendering from a
  mocked page (no overlay opening in jsdom).

### Phase 2 — Period reports

**Backend**

- `services/reports/periods.py`: `period_bounds(preset, today) -> (from,
  to)`; `services/reports/asof.py`: `status_as_of`, `due_as_of`,
  `existed_as_of` over `(item, events)`; `services/reports/build.py`:
  `build_period_report(db, program_id, *, from, to, filters, locale) ->
  PeriodReport`. Load items (`ItemFilters`, `include_deleted=True`), their
  updates, and audit events for `item`/`item_update` in one pass, then
  compute everything in memory.
- `schemas/reports.py`: `PeriodReport` with `summary`, `raised`,
  `completed`, `status_changes`, `updates`, `overdue_at_end`,
  `open_at_end`, `change_log`.
- `exporters/excel.py` refactor: extract `write_items_sheet(ws, rows,
  extra_columns=())` from `build_program_export` so the item export, the
  report's item sheets, and the translation column share one writer.
  Behaviour-preserving; the existing export tests are the guard.
- `exporters/report.py`: one function per sheet, `build_report_workbook`.
- `api/reports.py`: `GET /reports/period` (JSON) and
  `GET /reports/period.xlsx`.
- Tests: `test_periods.py` (month/quarter edges, leap years),
  `test_asof.py` (scripted history: create → status ×2 → due change →
  delete → restore; imported item with no events; item created after the
  date), `test_report_build.py` (summary figures on a fixture set),
  `test_reports_api.py` (params, filters, xlsx content type, sheet names).

**Frontend**

- `features/reports/`: `period.ts` (presets → from/to, mirrors the backend
  and is unit-tested), `useReport.ts`, `PeriodPicker.tsx`,
  `ScopeFilters.tsx` (subset of `FilterBar`), `ReportPreview.tsx`,
  `ReportsPage.tsx`, `ReportPrintPage.tsx`.
- `ReportPrintPage` is routed **outside** `AppLayout` (no sidebar or topbar)
  with a print stylesheet; it fetches the same JSON and renders tables.
- Sidebar entry "Reports"; Admin › Export page links to it.
- Tests: preset math, preview renders figures from a mocked report, print
  page renders every section heading.

### Phase 3 — Bilingual

Do it in this order, keeping the suite green after each step:

1. **Scaffold.** `src/i18n/index.ts` initializes i18next with `en` and
   `zh-CN` resources, the language detector, and `react-i18next`.
   `test/setup.ts` initializes it with `en` so existing tests keep matching
   English text. `<html lang>` follows the active language.
2. **Extract `en`.** Screen by screen, replace literal strings with
   `t("ns:key")`. `labels.ts` becomes functions of `t`. Run the ESLint rule
   as `warn` to find leftovers. Commit per feature folder.
3. **Write `zh-CN`.** Same keys. Add a Vitest test that both bundles have
   identical key sets. Hand the JSON to a GenSci reviewer early; fixes are
   JSON edits.
4. **Toggle and persistence.** Topbar `EN / 中文`; `PATCH /auth/me
   {locale}`; `useAuth` applies the stored locale on login.
5. **Audit summaries.** `audit-summary.ts` takes labels from `t`; the
   Phase 1 tests run under both locales.
6. **Item fields.** Migration `0002`: `user.locale`, `action_item.title_zh`
   / `details_zh`, `vocab_term.label_zh`, plus a data step that parses
   `provenance` (the raw "Translation in Mandarin" cell) with the same
   first-line / rest split as the importer. Schemas, `ItemForm` translation
   section, table second line, search fields, importer column, exporter
   column (via the Phase 2 `extra_columns` hook).
7. **Vocab labels.** `label_zh` column in Admin › Vocabularies; pickers and
   badges use `labelFor(term, locale)`.
8. **Export language.** `lang` query param on the item export, audit
   export, and report; backend labels from `app/i18n/labels.py`.

Migration testing: `tests/unit/test_migrations.py` already applies and
reverts on SQLite; add a case that seeds a v1-shaped row with provenance,
upgrades, and asserts the back-filled fields. The PostgreSQL CI job covers
the other engine.

### Phase 4 — Release

- Playwright: audit log filter + expand + export click; report download
  (assert the response content type); locale switch persists after reload.
- `@vitest/coverage-v8` with a 70% line threshold; ESLint i18n rule to
  `error`.
- Bump `backend/pyproject.toml` and `frontend/package.json` to `2.0.0`;
  `CHANGELOG.md`; `README.md` and `docs/DEPLOYMENT.md` sections for the
  locale, the audit log, and the reports; upgrade note ("take a backup of
  `/data/app.db`; `0002` is additive").
- Tag `v2.0.0`; `release.yml` publishes the image.

## 6. Test strategy summary

| Layer | Tool | What it guards in V2.0 |
|---|---|---|
| Backend unit | pytest | period bounds, as-of reconstruction, audit filters, label resolution, export row shaping, migration back-fill |
| Backend API | pytest + httpx | every new endpoint: happy path, auth failure, validation failure, admin gate |
| Frontend unit | Vitest + Testing Library | filter URL parsing, summary renderer in both locales, bundle key parity, preview and table rendering |
| E2E | Playwright | audit log, report download, locale switch, plus the v1 golden path |
| Migrations | existing CI job | `0002` applies and reverts on PostgreSQL |
| Container | existing smoke | still boots from a v1 `.env` with no new variables |

Known traps from the v1 dev logs, still true:

- Run backend tests with `uv run --python 3.13 pytest`; the pinned 3.14
  resolves to a release candidate that breaks pydantic locally.
- Opening a Radix overlay inside jsdom hangs the event loop. Test rendered
  output and hooks; leave open/close gestures to Playwright. The audit
  row expander should be a plain button toggling state, not a Radix
  Collapsible, for this reason.
- A leftover `backend/static/` directory makes the SPA mount shadow test
  routes; delete it before running the backend suite.

## 7. Commands every contributor runs

```bash
# backend
cd backend
uv sync
uv run --python 3.13 ruff check app tests && uv run --python 3.13 ruff format --check app tests
uv run --python 3.13 pytest --cov=app --cov-report=term-missing --cov-fail-under=80

# frontend
cd frontend
npm ci
npm run lint && npm run typecheck
npm test -- --coverage
npm run build

# after any backend DTO change
cd backend && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../frontend/openapi.json
cd ../frontend && npm run gen:api

# e2e (Chromium preinstalled in the sandbox; CI installs it)
cd frontend && npm run e2e
```

Recommended small addition in Phase 1: `scripts/check.sh` that runs all of
the above in order, so "green locally" means one command.

## 8. Effort

Relative to v1 phases (each of which was one plan and one PR):

| Phase | Backend tasks | Frontend tasks | Size |
|---|---|---|---|
| 1 Audit log | 5 | 5 | ~0.6 of a v1 phase |
| 2 Reports | 6 | 5 | ~0.8 |
| 3 Bilingual | 4 | 8 | ~1.2 |
| 4 Release | 1 | 3 | ~0.4 |

Phases 1 and 2 can overlap on separate branches once the exporter refactor
(Phase 2's first backend task) is merged, because Phase 1's export writer
and Phase 2's sheets both depend on it. If overlap is wanted, land that
refactor as its own small PR first.
