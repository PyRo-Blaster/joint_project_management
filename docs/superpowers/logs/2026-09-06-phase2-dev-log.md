# Phase 2 Development Log

Branch: `claude/phase-2-frontend-plan-p8h3e5`. Started 2026-09-06.
Records notable decisions, deviations, and fixes during Phase 2 (frontend core).
Routine "wrote file → tests passed → committed" steps are not logged; only
deviations, failures, and their resolutions are.

## Environment (this execution)
- node **v22.22.2**, npm 10.9.7 (plan assumed node 26; Vite 6 / React 19 / Tailwind v4
  all run on node 22, so no change needed for local dev/test/build).
- uv 0.8.17. Disk: ~30G free — ample for `npm install`.

### Blocker resolved before starting: backend venv on Python 3.14.0rc2
- **Symptom:** `uv run pytest` failed at import time with
  `AssertionError` in `pydantic/_internal/_typing_extra.py::eval_type_backport`
  (`assert isinstance(value, typing.ForwardRef)`), before any test ran.
- **Cause:** the pinned interpreter resolved to **CPython 3.14.0rc2** (a release
  candidate). pydantic 2.13's typing path is incompatible with that RC's typing
  internals. Not related to any Phase 2 change.
- **Fix (local only, no repo files changed):** rebuilt the venv on the stable
  **CPython 3.13.12** available in the image: `uv sync --python 3.13.12`, and run
  backend commands with `uv run --python 3.13.12 …`. `backend/.python-version`
  stays `3.14` for the Docker/CI path (the `python:3.14-slim` image ships a stable
  3.14, not an RC). Backend `requires-python = ">=3.13"`, so 3.13.12 is in range.
- **Baseline after fix:** `uv run --python 3.13.12 pytest` → 97 passed
  (data-dependent importer/export/CLI/bootstrap tests auto-skip; the confidential
  GS098 fixture is not present).

## Task-by-task notes

### T8 — backend user directory endpoint (done first, to seed generated types)
- Added `UserBrief` (id, name, org, is_active) and `GET /users/directory` guarded by
  `CurrentUser`. RED (404) → GREEN. Full backend suite **99 passed** (was 97), `ruff` clean.
- Executed before the frontend so `openapi.json`/`schema.d.ts` are generated once with
  `UserBrief` already present.

### T1–T2 — scaffold + design system
- **Deviation (ESLint 9):** the plan's `.eslintrc.cjs` is ignored by ESLint 9 (flat-config
  default). Replaced with `eslint.config.js` (flat) using the `typescript-eslint` meta-package +
  `@eslint/js` + `globals`, and `no-undef: off` (TS handles undefineds). `npm run lint` passes.
- **Fix (jsdom matchMedia):** `theme.test` crashed because jsdom has no `window.matchMedia`;
  the provider's `system` effect called it. Added a `matchMedia` stub to `test/setup.ts`.
- **Fix (TS config):** the plan's `tsconfig.node.json` project-reference tripped
  `composite`/`noEmit` errors, and `@types/node` was missing (vite.config uses `node:path`,
  `__dirname`). Collapsed to a single `tsconfig.json` (includes `src`, `test`, `vite.config.ts`;
  `types: [node, vitest/globals, jest-dom]`), added `@types/node`, and switched `build`/`typecheck`
  to `tsc --noEmit` (no build-mode/composite requirement). Removed `tsconfig.node.json`.
- Gates: `npm test` 2 passed (App, theme); `npm run build` clean (vite build → dist);
  `npm run lint` clean (0 errors, 1 harmless react-refresh warning).

### T3 — UI primitives + domain badges
- No surprises. 6 tests (format, button, StatusBadge + earlier). Prettier reflowed a few
  cva/interface lines; ran `npm run format` to keep the tree clean.

### T4–T5 — API layer + TanStack Query
- Generated `openapi.json` from the backend via
  `SECRET_KEY=… uv run --python 3.13.12 python -c "…create_app().openapi()"` (offline, no server),
  then `npm run gen:api`. All 9 DTOs (incl. `UserBrief`) present. Client/query tests 5 passed.

### T6–T7 — auth + app shell
- **Fix (Button `asChild`):** the plan's `<Button asChild={false}><Link/></Button>` doesn't
  compile — `Button` has no Radix Slot, and `<button><a>` is invalid HTML. Replaced with a
  `Link` styled by `buttonVariants()` in `NotFound` (and later `ItemDetailPage`).
- Kept `router.tsx` on placeholders (`ItemsPlaceholder`, no `/items/:id`) so this task builds
  green; the real pages are wired in T10 and T13.
- Gates: `npm test` 16 passed (9 files); `npm run build` clean. Bundle ~509 kB (159 kB gzip) —
  Vite's >500 kB note is informational; code-splitting is a Phase 3/hardening concern.

### T9–T11 — items table + filters
- **Fix (ItemsTable test):** a note row renders "Note" in both the Kind badge and the Status
  column (status is null → "Note"), so `getByText("Note")` matched two nodes. Switched to
  `getAllByText("Note")`. This is intended UI, not a bug.
- **Key finding — Radix overlays deadlock jsdom.** Opening any Radix overlay (Popover / Select /
  DropdownMenu) under jsdom hangs the event loop *synchronously* — vitest's own per-test timeout
  can't fire (a known Radix FocusScope/jsdom interaction). Added `matchMedia`, pointer-capture,
  `scrollIntoView`, `PointerEvent`, and `ResizeObserver` stubs to `test/setup.ts` (all needed for
  Radix to render at all), but click-to-open still hard-hangs. **Rendering closed overlays is
  fine** — only opening them hangs — so every other component test (ItemForm/detail/updates/
  history) renders closed selects or clicks plain buttons and is unaffected. Reworked the
  FilterBar test to cover the debounced search, the active-count badge (reflects `selected`
  without opening), and the clear affordance. The open→select interaction is verified against the
  real dev server instead.
- Gates: items suite 7 passed; `npm test` all green; typecheck + build clean.

### T12–T13 — item create + detail
- **Fix (`ItemDetailPage` Button `asChild`):** same as `NotFound` — styled the `Link` with
  `buttonVariants()` instead of the unsupported `<Button asChild>`.
- Reused `ItemForm` for both the New-item dialog and the detail Details tab (via
  `itemToFormValues`). `kind` is sent on PATCH but ignored server-side (immutable). Confirmed
  that rendering `ItemDetail` (which mounts ItemForm's closed Radix selects) does **not** hang —
  only *opening* a Radix overlay hangs jsdom. 3 tests passed.

### T14–T15 — updates + history
- No surprises. Timeline compose/edit/delete and the audit-diff history render via plain buttons
  (no overlays), so tests are fast and reliable. item-detail suite green.

### T16–T17 — serve SPA from container + final gates
- **SPA fallback:** added `SPAStaticFiles` to `app/main.py`; RED (`/items/42` → 404) → GREEN.
  Backend **100 passed** (was 99), ruff clean. The existing `/api` envelope-404 test still passes
  (the fallback re-raises for `api/*`).
- **End-to-end validation without Docker** (the sandbox has the docker CLI but no daemon): built
  the frontend, copied `dist` → `backend/static`, ran uvicorn on 3.13.12, and curled:
  `/api/health` → `database: ok`; `/` and `/items/5` → 200 `text/html` (SPA shell, deep link
  survives); `/assets/<hash>.js` → 200 `text/javascript`; `/api/does-not-exist` → 404 envelope
  `http_error`; `/api/auth/me` → 401 envelope `unauthenticated`. All correct.
- **Dockerfile:** added a `frontend-build` stage. Used `node:22-slim` (matches the local toolchain
  that generated `package-lock.json` and built cleanly here) rather than the plan's `node:26`.
  The image build itself is deferred to Phase 4 CI (no docker daemon here); the *serving behavior*
  it produces is already validated above. Added `backend/static/` to `.gitignore` and a
  `frontend/.prettierignore` (generated `openapi.json`/`schema.d.ts`).

## Phase 2 result
All tasks complete. **28 frontend tests (Vitest, 16 files) + 100 backend tests** passing;
`ruff` and ESLint/Prettier clean (4 non-fatal react-refresh warnings on provider+hook files);
`npm run build` and `npm run typecheck` green. The single-container serving path (API + built
SPA + client-side-routing fallback) is validated end-to-end locally. Docker image build and
Playwright e2e remain for Phase 4.
