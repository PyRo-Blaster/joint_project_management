# V2.0 — Debugging, Testing, and Performance Review Plan

Date: 2026-09-16
Status: Draft for user review
Companion to `2026-09-16-v2-design.md` (what) and
`2026-09-16-v2-implementation-approach.md` (how). This document says how
each iteration is debugged, verified, measured, and reviewed before it
reaches the two teams.

## 1. The iteration loop

Every phase (and every hotfix) goes through the same loop. Nothing skips a
stage; a hotfix just moves through it in hours instead of weeks.

```
plan → build (TDD) → local checks → PR + CI → staging container → UAT → tag → observe → retro
```

| Stage | Gate | Evidence |
|---|---|---|
| Build | Failing test written before the code for every task | Commit history shows RED → GREEN pairs |
| Local checks | `scripts/check.sh` green | Pasted into the PR description |
| PR + CI | All CI jobs green, review approved | GitHub checks |
| Staging | Pre-release image deployed on a copy of production data | Dev log entry with the tag and date |
| UAT | Phase checklist walked through by one person from each org | Checklist ticked in the PR or the dev log |
| Tag | Acceptance criteria in the design spec §10 met for the shipped scope | Release notes |
| Observe | One week of logs and issues reviewed after release | Retro notes in the dev log |

## 2. Debugging

### 2.1 What v1 already provides

- Every response carries `X-Request-Id`; unexpected errors log the id, the
  path, and the stack trace, and the UI shows the id in the error toast.
  A user reporting "request id abc123" is the starting point for every
  backend investigation.
- `LOG_LEVEL=debug` in `.env` raises the app logger; the request id is in
  every log line for that request.
- `GET /api/docs` (Swagger) lets you call any endpoint with the browser's
  session cookie, which is the fastest way to isolate "is it the API or the
  UI".
- The audit trail itself: when a user reports "the item changed by itself",
  the History tab and, from Phase 1, the Audit log page answer who and when
  before any code is read.
- Playwright records a trace on the first retry in CI; `npx playwright
  show-trace` replays it step by step with DOM snapshots and network.

### 2.2 Additions for V2.0

| Addition | Where | Purpose |
|---|---|---|
| Request timing | `request_context` middleware in `app/main.py` adds `X-Response-Time` (ms) and logs `method path status duration_ms request_id user_id` at INFO for `/api/*` | Every slow report or audit query is visible in `docker compose logs` without a profiler. |
| SQL echo switch | `SQL_ECHO=true` env var → `create_engine(echo=True)` | Shows the exact statements behind a slow page; off by default. |
| Structured log format | One JSON line per log event when `LOG_FORMAT=json` (stdlib `logging` formatter, no library) | Lets `docker compose logs app \| jq` filter by request id or user. |
| Report explainer CLI | `python -m app.cli report-explain --item 42 --as-of 2026-08-31` prints the item's event replay and the resulting as-of status and due date | The as-of reconstruction is the one piece of V2.0 logic a user can dispute ("it says this was open on Aug 31, it was not"); this makes the answer reproducible in seconds. |
| Audit explainer CLI | `python -m app.cli audit --item 42 --since 2026-08-01` prints events as a table | Same for "who changed this", usable over SSH when the UI is not at hand. |
| Query devtools in dev | `@tanstack/react-query-devtools` mounted only when `import.meta.env.DEV` | Diagnoses refetch storms and stale caches on the audit and report pages. |
| Demo data seeder | `scripts/seed_demo.py --items 2000 --updates 6000 --events 40000 --days 540` writes a synthetic program into a throwaway database | One command reproduces "it is slow with more data" and gives reviewers something to click through without confidential data. |

### 2.3 Rules

- **Reproduce as a test first.** Issue #4 (toggle action ↔ note would not
  save) was fixed that way; keep it. A bug report becomes a failing unit or
  API test in the same commit as the fix, named after the issue.
- **Never debug on production data in place.** Copy `/data/app.db` to a
  local file and run the CLI or the app against it with
  `DATABASE_URL=sqlite:///./copy.db`. The audit and report explainers are
  read-only by construction.
- **Frontend bugs get a request id or a trace.** A UI bug report is
  accompanied by the failing request's id (from the toast) or, for
  interaction bugs, a Playwright trace reproduced locally with
  `npm run e2e -- --trace on`.
- **Container-level checks in order:** `docker compose ps` (health),
  `docker compose logs --since 1h app`, `curl /api/health`, then
  `docker compose exec app python -m app.cli …` for the explainers.

## 3. Testing

### 3.1 Layers and what each one owns

| Layer | Runs | Owns in V2.0 | Target |
|---|---|---|---|
| Backend unit (pytest) | every commit, < 10 s | period bounds; as-of reconstruction; audit filters and label resolution; export row shaping; i18n label tables; migration `0002` back-fill | 80% coverage gate (existing) |
| Backend API (pytest + httpx) | every commit | every new endpoint: happy path, auth failure, validation failure, admin gate, row cap, `lang` param | same gate |
| Frontend unit (Vitest + Testing Library) | every commit, < 20 s | filter URL parsing, summary renderer in both locales, bundle key parity, audit table and report preview rendering | 70% line gate (new) |
| Migrations | CI (PostgreSQL job) and unit (SQLite) | `0002` applies, back-fills, reverts | must pass |
| E2E (Playwright) | CI and before tag | golden path (v1) + audit log filter/expand/export, report download, locale switch persistence | must pass |
| Container smoke | CI | v1 `.env` still boots; create an item; health ok | must pass |
| Upgrade test | CI, new job | boot the last released image with seeded demo data, stop it, boot the candidate on the same volume, assert migrations applied and counts unchanged and `title_zh` back-filled | must pass |

### 3.2 Test data

- **Synthetic fixture** (`tests/fixtures/synthetic.py`, 5 rows) stays the
  unit-test workhorse; extend it with a Mandarin translation cell and a
  scripted history so the as-of and bilingual tests have known answers.
- **Scripted histories** for reports are written as small DSL lists in the
  test, e.g. `[("create", d0, "open"), ("status", d1, "in_progress"),
  ("delete", d2), ("restore", d3)]`, expanded into `audit_event` rows by a
  helper, so each edge case is one readable line.
- **Demo seeder** (§2.2) produces the volume set for performance, the
  upgrade job, and staging. It is deterministic (`--seed 1`) so numbers are
  comparable run to run.
- **Real GS098 sheet** stays uncommitted; the tests that need it keep
  skipping when absent, and a maintainer runs the full suite with it before
  each tag.

### 3.3 Manual and user acceptance testing

Each phase PR includes a short UAT checklist; the staging container runs
the pre-release tag against a **copy** of the production volume so the
reviewers see real items.

- **Phase 1 (audit log):** find who changed item #N last month; filter by
  actor; expand a row and confirm old → new matches the item's History
  tab; export and open in Excel; confirm sign-ins appear only with the
  filter on; confirm members cannot open `/admin/audit`.
- **Phase 2 (reports):** run "Last month" and compare the Summary sheet's
  "open at period end" with what the dashboard showed on that date (one
  screenshot kept from the last day of each month from now on); open the
  printable page and save to PDF; confirm the Completed sheet lists the
  items the teams remember closing.
- **Phase 3 (bilingual):** a GenSci reviewer reads every screen in 中文 and
  files wording issues as a JSON diff; a Yarrow reviewer confirms English
  is unchanged; both confirm the toggle persists across browsers; import
  the last export and confirm the translation column round-trips.
- **Release:** the design spec's §10 acceptance list walked through end to
  end by both reviewers on staging.

Findings go to GitHub issues labelled `phase-N` and `uat`; a phase is not
tagged with an open `uat` issue of severity "blocks use".

## 4. Performance

### 4.1 Budgets

Measured on the demo seeder's default volume (about 35× the current
program: 2 000 items, 6 000 updates, 40 000 audit events) on a 2-vCPU
container with SQLite, warm cache, single user. p95 over 20 requests.

| Operation | Budget | Rationale |
|---|---|---|
| `GET /items` page of 50 | 150 ms | v1 baseline; must not regress from the extra `_zh` search columns |
| `GET /activity` page of 50 with filters | 200 ms | needs the two new indexes |
| `GET /activity/export` at 50 000 rows | 10 s | openpyxl is the ceiling; beyond that the cap warns |
| `GET /reports/period` (one quarter) JSON | 2 s | in-memory replay over one quarter's events |
| `GET /reports/period.xlsx` | 5 s | JSON + eight sheets |
| `GET /dashboard/summary` | 300 ms | unchanged code path; guards the sign-in event exclusion |
| Frontend initial JS (gzipped) | 350 KB | v1 plus i18n runtime and two bundles; `zh-CN` lazy-loaded so English users pay nothing |
| Audit page first render (50 rows) | 100 ms scripting | hand-rolled table, no virtualization needed at 50 rows |
| Locale switch | 200 ms | bundle already cached after first load |
| Container RSS at idle | 250 MB | unchanged single process |

### 4.2 How it is measured

- **Backend micro-benchmarks:** a `perf` pytest marker (excluded by default,
  run with `pytest -m perf`) loads the seeded database once per session and
  times each budgeted endpoint through the test client, asserting the p95
  against the table. Numbers are printed so the dev log can record them.
- **Query count assertions:** a `count_queries()` fixture (SQLAlchemy
  `before_cursor_execute` listener) wraps the audit list, label resolution,
  and report build; tests assert an upper bound (e.g. audit page ≤ 4
  statements regardless of row count) so N+1 regressions fail fast rather
  than showing up as latency.
- **Query plans:** for the new audit filters, a unit test runs `EXPLAIN
  QUERY PLAN` on SQLite and asserts the `(actor_id, occurred_at)` or
  `(entity_type, entity_id)` index is used; the PostgreSQL CI job runs
  `EXPLAIN` and prints it to the log for review.
- **Frontend bundle:** `vite build` output sizes are parsed by
  `scripts/bundle-budget.mjs`, which fails CI when the gzipped entry chunk
  exceeds the budget; `rollup-plugin-visualizer` is available as a dev
  script for finding what grew.
- **Frontend runtime:** React Profiler in dev for the audit table and
  report preview; Chrome DevTools Lighthouse run manually on staging for
  each pre-release tag (performance and accessibility scores recorded in
  the dev log).
- **Production signal:** the `duration_ms` field in the request log. A
  weekly `docker compose logs --since 168h app | jq` recipe in
  `DEPLOYMENT.md` prints p50 / p95 per route; anything over budget opens an
  issue.

### 4.3 Design choices that keep V2.0 inside budget

- Audit `entity_label` is resolved with one `IN` query per entity type per
  page, never per row.
- The report loads items, updates, and events with three queries filtered
  by program and date window, then computes in memory; no per-item queries.
- `zh-CN` resources are a separate chunk (`import()` on switch); the
  English bundle is inlined.
- Export endpoints stream `BytesIO` and set `Content-Disposition`; no temp
  files.
- SQLite runs in WAL mode (`PRAGMA journal_mode=WAL` alongside the existing
  foreign-key pragma) so the audit log page can read while another user
  writes; this is a one-line change in `app/db.py` with a test.

### 4.4 Regression rule

Each phase's dev log has a "Performance" table: every budgeted operation
before and after the phase on the same seeded database. A regression above
20% blocks the tag until it is either fixed or explicitly accepted with a
reason in the log.

## 5. Review

### 5.1 Code review

Every PR gets one human review plus automated review, with a template
(`.github/pull_request_template.md`, new) that asks for:

- link to the plan task(s) and the spec section;
- tests added (unit / API / frontend / e2e) and the local check output;
- migration reversibility confirmed (`alembic downgrade -1` run locally);
- OpenAPI types regenerated if any DTO changed;
- i18n: new strings keyed in both bundles (Phase 3 onward);
- docs touched (`README`, `DEPLOYMENT.md`, dev log);
- performance table if a budgeted endpoint was touched.

Automated review on each PR: the `code-review` skill at medium effort for
correctness, and the `security-review` skill on any PR touching auth,
export, or the audit log (sign-in events, admin gates, row caps, no
password material in `changes`). Findings are addressed or answered in
the thread before merge.

Review checklist specific to V2.0 code:

- Audit events are never edited or deleted by any new code path.
- Security actions are excluded from the dashboard feed and from
  non-admin views.
- Every export honours `lang` and the requesting user's role.
- As-of functions take `day` as a parameter; nothing reads the wall clock
  except the router.
- No literal user-facing string outside the bundles (lint enforces).

### 5.2 Release readiness review

Before `v2.0.0`: a one-hour session with one admin from each org on
staging walking the design spec §10 acceptance list, the performance table
from the last dev log, the open issue list, and the upgrade note. The
outcome is recorded in `docs/superpowers/logs/…-v2-release-review.md`
with go / no-go and any accepted deviations.

### 5.3 Post-release observation and retro

For the first week after each tag: daily look at `docker compose logs` for
5xx and request ids, the GitHub issue queue, and the p95 recipe. At the end
of the phase a short retro section in the dev log answers three questions:
what broke that the tests did not catch, what slowed the loop, and what to
change in the next plan. Those answers feed the next phase's plan header,
the same way the v1 logs' "testing reality" notes did.
