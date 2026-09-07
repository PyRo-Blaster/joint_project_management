# Phase 2: Frontend Core — Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking.
> Prefer focused commits; update `docs/superpowers/implementation-checklist.md` as items land.

**Goal:** Deliver a production-ready React UI (login, items table, item detail with timeline + history) built into the same Docker image as the Phase 1 API so both teams can use the tracker from one container.

**Architecture:** Vite + React 19 + TypeScript + Tailwind CSS app under `frontend/`. TanStack Query owns server state; react-hook-form + zod mirror backend schemas; a thin envelope-aware fetch layer wraps a generated OpenAPI TypeScript client. FastAPI continues to serve the built assets from `static/` (html=True SPA fallback). Dev mode: Vite on :5173 proxies `/api` to uvicorn :8000.

**Tech Stack:** Node ≥ 20, Vite 6, React 19, TypeScript 5.7, Tailwind CSS 3.4, TanStack Query 5, React Router 7, react-hook-form + zod, openapi-typescript, lucide-react, sonner (toasts).

**Spec:** `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md` §10 Frontend. Phase 3 owns Kanban, dashboard tiles, and admin screens — Phase 2 ships a minimal post-login redirect to Items and placeholder routes only where needed for navigation.

---

## Conventions

- Repository root: work from repo root. Frontend commands: `cd frontend && …`.
- Every commit message ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- English UI only. Mutations always send `X-Requested-With: fetch`. Session cookie auth (`credentials: 'include'`).
- Envelope `{success, data, error, meta}`: success path returns `data` (+ optional `meta`); failures throw `ApiError` with `code`, `message`, `fields`, `requestId`, `status`.
- URL-synced item filters: search params are the source of truth (shareable links).
- Do not commit secrets, `.env`, or confidential xlsx files.

## File structure

```
frontend/
├── package.json
├── vite.config.ts              # React plugin, /api proxy, path alias @/
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── tailwind.config.js / postcss.config.js / index.html
├── scripts/generate-api.mjs    # fetches OpenAPI → src/lib/api/schema.d.ts
├── src/
│   ├── main.tsx / index.css
│   ├── app/                    # App, router, providers, layout, error-boundary
│   ├── features/auth/          # login, accept-invite, auth context/guard
│   ├── features/items/         # table, filters, detail sheet, history, forms
│   ├── components/ui/          # button, input, select, sheet, badge, …
│   └── lib/                    # api client, query keys, constants, utils, format
backend/app/static/             # build output target (gitignored except .gitkeep)
Dockerfile                      # Node build stage → copy into runtime static/
```

---

### Task 1: Phase 2 plan + checklist hook

**Files:** this plan; tick first checklist row when committed.

- [x] Write this plan under `docs/superpowers/plans/`.
- [ ] Commit: `docs: add Phase 2 frontend core implementation plan`

### Task 2: Vite + React + TS + Tailwind scaffold + app shell

**Files:** `frontend/*` scaffold; `src/app/*` router/providers/layout.

- [ ] `package.json` with deps listed above; scripts: `dev`, `build`, `preview`, `generate:api`, `typecheck`.
- [ ] Tailwind + CSS variables (light/dark-ready neutrals, one accent, semantic status/priority colors).
- [ ] App shell: `BrowserRouter`, `QueryClientProvider`, `AuthProvider`, `Toaster`, `ErrorBoundary`.
- [ ] Layout: top nav (Items, placeholders for Dashboard/Board/Admin), user menu + logout.
- [ ] Routes: `/login`, `/accept-invite`, `/items`, `/items/:itemId`, catch-all → `/items`.
- [ ] Gate: install deps, then `typecheck` in `frontend/`.
- [ ] Commit: `feat(frontend): scaffold Vite React TS Tailwind app shell`

### Task 3: Generated TypeScript client from OpenAPI

**Files:** `frontend/scripts/generate-api.mjs`, `frontend/src/lib/api/schema.d.ts`, `frontend/src/lib/api/client.ts`, short note in README.

- [ ] Script loads OpenAPI from `OPENAPI_URL` (default `http://localhost:8000/api/openapi.json`) or `OPENAPI_FILE`, runs openapi-typescript, writes `src/lib/api/schema.d.ts`.
- [ ] Envelope-aware `api` helper: GET/POST/PATCH/DELETE, CSRF header on mutations, cookie credentials, unwrap envelope, map 401 → session-expiry event.
- [ ] Document regenerate: start API → `cd frontend &&` run `generate:api` script.
- [ ] Commit: `feat(frontend): add OpenAPI types and envelope-aware API client`

### Task 4: Auth — login, accept-invite/reset, session expiry, error boundary

**Files:** `features/auth/*`, wire into router/layout.

- [ ] Login form (email/password) → `POST /api/auth/login`; redirect to `/items`.
- [ ] Accept-invite page (token from `?token=`): name + password (≥10) → `POST /api/auth/accept-invite` → login redirect.
- [ ] `AuthProvider` loads `GET /api/auth/me`; `RequireAuth` guard; logout via `POST /api/auth/logout`.
- [ ] On 401 from API layer: clear user, toast, navigate to `/login?next=…`.
- [ ] Global `ErrorBoundary` with request-id-friendly fallback UI.
- [ ] Commit: `feat(frontend): auth login, accept-invite, session expiry, error boundary`

### Task 5: Items table — sort, filters, search, columns, URL sync

**Files:** `features/items/*` table + filter bar + column visibility.

- [ ] `GET /api/items` with query from URL: `status`, `priority`, `group`, `category`, `owner_org`, `kind`, `assignee_id`, `due_before`, `due_after`, `q`, `sort`, `direction`, `page`, `limit`.
- [ ] Sortable headers; filter bar multi-selects + search; column visibility persisted in `localStorage`.
- [ ] Vocab terms + users loaded for filter options (`GET /api/vocab`, `GET /api/users` — users may 403 for members; degrade gracefully).
- [ ] Row click opens detail sheet / navigates to `/items/:id` keeping list filters in URL.
- [ ] Commit: `feat(frontend): items table with URL-synced filters and column visibility`

### Task 6: Item detail — sheet + deep link, edit, timeline, history

**Files:** `features/items/detail*`, updates compose, history tab.

- [ ] Side sheet over list when on `/items/:itemId`; works as deep link.
- [ ] Editable fields via react-hook-form + zod (`ItemPatch`); save → `PATCH /api/items/{id}`; inline field errors from envelope `error.fields`; success toast.
- [ ] Updates tab: list `GET …/updates`, compose box `POST …/updates`.
- [ ] History tab: `GET …/history` with per-field old → new diffs.
- [ ] Commit: `feat(frontend): item detail sheet with edit, timeline, and history`

### Task 7: Envelope API layer polish (Query + forms + toasts)

- [ ] Shared mutation helpers set field errors on RHF and toast operation results.
- [ ] Query keys: `['auth','me']`, `['items', filters]`, `['item', id]`, `['item', id, 'updates']`, `['item', id, 'history']`, `['vocab']`, `['users']`.
- [ ] Commit if not already covered: `feat(frontend): TanStack Query keys and form error/toast helpers`

### Task 8: Dockerfile Node stage + static serve

**Files:** `Dockerfile`, `backend/app/static/.gitkeep`, README tweak, checklist.

- [ ] Multi-stage: `frontend-build` (node:22-bookworm) → install + build; copy into image `/app/static`.
- [ ] Runtime stage copies static assets; existing `StaticFiles(html=True)` serves SPA.
- [ ] Gate: `docker compose build` (when Docker available); otherwise document blocker and verify production build locally.
- [ ] Update checklist Phase 2 rows; README frontend dev notes.
- [ ] Commit: `feat: build frontend into image static/ via Node Docker stage`

### Task 9: Push PR

- [ ] Push `phase2-frontend-core` (no force, not to main).
- [ ] Open PR summarizing Phase 2 slice and verify steps.

---

## Verify

```bash
# Frontend typecheck + production build
cd frontend
# install deps, generate:api, typecheck, build (see package.json scripts)

# Dev: API + Vite
# terminal 1 — backend
cd backend && uv run uvicorn app.main:app --reload --port 8000
# terminal 2 — frontend
cd frontend   # run dev script → http://localhost:5173

# Container (needs Docker)
docker compose up -d --build
# open http://localhost:8000/ → login UI
```

## Out of scope (Phase 3+)

Kanban board, dashboard tiles/activity UI, admin (users/invites/vocab/import/export) screens, Vitest suite, Playwright e2e, CI image publish.
