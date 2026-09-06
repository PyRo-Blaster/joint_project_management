# Joint CMC Action Tracker — Design Spec

Date: 2026-09-06
Status: Draft for user review
Program: GS098 (GenSci × Yarrow joint CMC program)

## 1. Purpose

Replace the shared Excel "Master Track Sheet" with a web app that both teams
(GenSci and Yarrow) use to track CMC action items and decisions. The app must:

- give every person their own account and attribute every change to them;
- keep a complete change history (who changed what, when, old → new);
- show a dashboard of recent activity and items that need attention;
- import the existing spreadsheet once and export a familiar-looking xlsx on
  demand;
- look and feel like a polished modern product, not an admin scaffold.

## 2. Decisions already made

| Topic | Decision |
|---|---|
| Deployment | Docker-first. `docker compose up -d` is the only supported way to run the app, locally and on a server. One application image, SQLite on a volume by default; PostgreSQL and an HTTPS proxy are optional compose profiles. Nothing is built on the server. |
| Excel | One-time import. The app is the master afterwards. Export xlsx on demand. |
| Programs | Single program (GS098) in the UI. A `program` entity exists so more programs can be added later without a migration of item data. |
| Accounts | Invite-only. Roles: `admin`, `member`. Each user is tagged `gensci` or `yarrow`. |
| Audit | Every write, including admin actions, is logged against the acting user. |
| Language | English UI and English item text. The Mandarin column is retained only inside the import provenance JSON. |
| Stack | FastAPI + SQLAlchemy 2 + Alembic + openpyxl backend; React + Vite + TypeScript + Tailwind frontend. SQLite locally, PostgreSQL when deployed. |
| Views | Items table, Kanban board, item detail, dashboard, admin area. |

## 3. Scope

### In scope for v1

- Authentication (login, logout, accept invitation, admin-generated password
  reset link).
- User administration (invite, deactivate, change role/org, reset link).
- Action items: create, edit, soft delete, restore; controlled vocabularies
  for group and category.
- Item updates (dated timeline entries replacing the "Status Updates" cell).
- Audit log with per-field diffs; History tab per item; global activity feed.
- Items table with filters, search, sort, column visibility.
- Kanban board with drag-and-drop between status columns.
- Dashboard: stat tiles, needs-attention list, activity feed, breakdowns.
- Excel import (preview → commit) and export.
- Docker-first packaging: single image, compose file, self-configuring
  startup (migrate, seed admin, optional initial import), optional Postgres
  and HTTPS profiles, health check, and a deployment note.

### Out of scope for v1 (model leaves room)

- File uploads/attachments (file path stays a text pointer into the shared
  document tree).
- Email sending. Invitation and reset links are shown to the admin to send
  manually.
- Notifications, reminders, or scheduled digests.
- Multi-program UI, program switcher, per-program membership.
- Translated UI or a first-class translation field.
- The Sheet2 document checklist.
- Manual card ordering inside Kanban columns.

## 4. Architecture

```
joint_cmc_management/
├── backend/                 # uv-managed Python 3.14 project
│   ├── app/
│   │   ├── main.py          # FastAPI app factory, static file serving in prod
│   │   ├── config.py        # pydantic-settings; fails fast on missing secrets
│   │   ├── db.py            # engine/session factory
│   │   ├── models/          # one SQLAlchemy model per file
│   │   ├── schemas/         # pydantic request/response models per feature
│   │   ├── api/             # routers per feature; thin, no DB access
│   │   ├── services/        # business logic + audit; the only DB writers
│   │   ├── importers/excel/ # parse, normalize, preview, commit
│   │   └── cli.py           # seed-admin, import-excel, export-excel
│   ├── alembic/
│   └── tests/               # unit/, api/, fixtures/ (copy of the xlsx)
├── frontend/                # Vite + React + TypeScript
│   ├── src/
│   │   ├── app/             # router, providers, layout shell
│   │   ├── features/        # auth, dashboard, items, board, admin
│   │   ├── components/ui/   # shadcn-style primitives
│   │   └── lib/             # typed API client, formatting, constants
│   └── e2e/                 # Playwright
├── Dockerfile               # multi-stage: node build → uv deps → slim runtime
├── docker-compose.yml       # app service + optional `postgres` and `proxy` profiles
├── .env.example             # every variable, documented
├── .github/workflows/       # tests on push; build + publish image on tag
├── docs/superpowers/specs/  # this document and its successors
└── resources/               # original spreadsheet
```

Principles:

- **Service layer owns writes.** Routers validate with pydantic, call a
  service, and return an envelope. Services open a unit of work, apply the
  change, write the audit event in the same transaction, and return fresh
  pydantic DTOs. ORM mutation is confined to the service unit of work.
- **Engine-neutral schema.** Only column types and constraints that behave
  the same on SQLite and PostgreSQL are used (`JSON` column via SQLAlchemy,
  no arrays, no partial indexes). One `DATABASE_URL` switches engines.
- **One image, one command.** A multi-stage Dockerfile builds the frontend
  in a Node stage, installs backend dependencies with uv in a second stage,
  and copies both into a slim Python runtime image that serves the API and
  the built frontend on one port. For hot-reload development FastAPI (:8000)
  and Vite (:5173, proxying `/api`) can also run directly on the host; that
  is a convenience, not a deployment path.
- **Small files.** Target 200–400 lines per module, 800 max. Split by
  feature, not by layer, within `features/` and `services/`.

### Deployment

Goal: a new server needs Docker and one directory containing
`docker-compose.yml` and `.env`. No build tools, no manual migration, seed,
or import steps.

- **Startup is self-configuring and idempotent.** The container entrypoint
  runs `alembic upgrade head`; creates the first admin from `ADMIN_EMAIL` and
  `ADMIN_PASSWORD` if no users exist; seeds the GS098 program and vocab terms
  if missing; and, when `INITIAL_IMPORT_PATH` points at a mounted xlsx and the
  program has no items, imports it. Restarts and upgrades are therefore just
  `docker compose pull && docker compose up -d`.
- **SQLite by default.** The database file lives on a named volume
  `app-data`, so a backup is a copy of one file. `--profile postgres` adds a
  PostgreSQL service and points `DATABASE_URL` at it; the same migrations
  apply.
- **HTTPS is one flag.** `--profile proxy` adds a Caddy service that
  terminates TLS for `DOMAIN` with automatic certificates. Without it the app
  listens on `APP_PORT` (default 8000) for use on an intranet or behind an
  existing reverse proxy.
- **Images are built once, never on the server.** `docker compose build` on
  a developer machine, then either push to a registry (the GitHub Actions
  workflow publishes to GHCR on version tags) or `docker save` to a tarball
  that is copied and `docker load`ed where registry access is slow or
  blocked. `docker-compose.yml` references the image by tag; the Dockerfile
  is only needed to build.
- **Health check.** `GET /api/health` returns version and database status;
  compose uses it as `healthcheck`, so `docker compose ps` shows readiness
  and the proxy waits for it.

## 5. Data model

All tables have an integer primary key `id` and UTC `created_at`. Enum-like
columns are stored as short lowercase strings validated in pydantic and
constrained with a CHECK.

### program
| Field | Type | Notes |
|---|---|---|
| code | str, unique | `GS098` |
| name | str | |

### user
| Field | Type | Notes |
|---|---|---|
| email | str, unique, lowercased | login identifier |
| name | str | display name |
| password_hash | str | argon2id |
| org | `gensci` \| `yarrow` | |
| role | `admin` \| `member` | |
| is_active | bool | deactivated users cannot log in; history stays |
| last_login_at | datetime, nullable | |

### session
| Field | Type | Notes |
|---|---|---|
| token_hash | str, unique | SHA-256 of the cookie value |
| user_id | FK user | |
| expires_at | datetime | `SESSION_TTL_HOURS`, default 72 |
| last_seen_at | datetime | sliding expiry |

### invitation
| Field | Type | Notes |
|---|---|---|
| purpose | `invite` \| `reset` | reset reuses the same link flow |
| email | str | |
| org, role | as user | ignored for `reset` |
| user_id | FK user, nullable | set for `reset` |
| token_hash | str, unique | 32 random bytes, hashed at rest |
| expires_at | datetime | `INVITE_TTL_DAYS`, default 7 |
| accepted_at | datetime, nullable | |
| created_by | FK user | |

### action_item
| Field | Type | Notes |
|---|---|---|
| program_id | FK program | |
| entry_no | int | unique within program; imported as-is, new items get max+1 |
| kind | `action` \| `note` | notes are recorded decisions/observations |
| title | str ≤ 500 | required |
| details | text | optional long description |
| group | str | must match an active `vocab_term(field=group)` |
| category | str, nullable | must match `vocab_term(field=category)` |
| owner_org | `gensci` \| `yarrow` \| `joint` | |
| assignee_id | FK user, nullable | accountable person |
| status | `open` \| `in_progress` \| `blocked` \| `on_hold` \| `completed` \| `cancelled`, nullable | null if and only if `kind = note` |
| priority | `p1` \| `p2` \| `p3`, nullable | |
| raised_on | date | |
| source | str, nullable | e.g. `Meeting 2026-02-05 to 2026-02-06` |
| due_on | date, nullable | the sheet's Checkpoint/DDL |
| completed_on | date, nullable | set when status becomes `completed` |
| notes_risks | text | |
| file_path | str | pointer into the shared document tree |
| provenance | JSON, nullable | raw imported row incl. Mandarin translation |
| created_by, updated_by | FK user | |
| updated_at | datetime | |
| deleted_at, deleted_by | nullable | soft delete |

### item_update
| Field | Type | Notes |
|---|---|---|
| item_id | FK action_item | |
| author_id | FK user | |
| body | text | required, non-empty |
| occurred_on | date | defaults to today; import sets from `UPDATE-YYYYMMDD` |
| edited_at | datetime, nullable | |

### vocab_term
| Field | Type | Notes |
|---|---|---|
| program_id | FK program | |
| field | `group` \| `category` | |
| value | str | unique per (program, field) |
| sort_order | int | |
| is_active | bool | inactive terms stay valid on old items, hidden from pickers |

### audit_event
| Field | Type | Notes |
|---|---|---|
| program_id | FK program, nullable | null for user-admin events |
| entity_type | `item` \| `item_update` \| `user` \| `invitation` \| `vocab_term` \| `import` | |
| entity_id | int | |
| action | `created` \| `updated` \| `deleted` \| `restored` \| `status_changed` \| `update_posted` \| `role_changed` \| `deactivated` \| `reactivated` \| `invited` \| `revoked` \| `imported` | |
| actor_id | FK user | never null; CLI commands take `--actor EMAIL`, defaulting to the seeded admin |
| occurred_at | datetime | |
| changes | JSON | `{field: {"old": x, "new": y}}`; empty for creates |
| summary | str | human line for the feed, e.g. `changed status In progress → Blocked` |

Indexes: `action_item(program_id, status)`, `action_item(program_id, due_on)`,
`item_update(item_id, occurred_on)`, `audit_event(occurred_at)`,
`audit_event(entity_type, entity_id)`.

## 6. Permissions

| Capability | member | admin |
|---|---|---|
| View items, board, dashboard, history | ✓ | ✓ |
| Create/edit items, change status, post/edit own updates | ✓ | ✓ |
| Soft delete items | ✓ | ✓ |
| Restore items, edit/delete others' updates | | ✓ |
| Manage users, invitations, reset links | | ✓ |
| Manage vocab terms | | ✓ |
| Import Excel | | ✓ |
| Export Excel | ✓ | ✓ |

Both orgs see and edit everything; the org tag is for attribution and
filtering, not access control. A user cannot change their own role or
deactivate themselves. The last active admin cannot be demoted or deactivated.

## 7. API

REST under `/api`, JSON only. Every response uses the envelope:

```json
{ "success": true, "data": …, "error": null, "meta": { "total": 57, "page": 1, "limit": 50 } }
{ "success": false, "data": null, "error": { "code": "validation_error", "message": "…", "fields": { "title": "required" } }, "meta": null }
```

Mutating requests must carry header `X-Requested-With: fetch` (CSRF defence
alongside `SameSite=Lax`).

| Method & path | Purpose | Role |
|---|---|---|
| POST `/auth/login`, POST `/auth/logout`, GET `/auth/me` | session auth | any |
| POST `/auth/accept-invite` | set name + password from an invite or reset token | public |
| GET/POST `/users`, PATCH `/users/{id}` | list, create (via invitation), edit role/org/name/active | admin |
| POST `/users/{id}/reset-link` | create a `reset` invitation, return the URL once | admin |
| GET/POST `/invitations`, DELETE `/invitations/{id}` | list, create (returns URL once), revoke | admin |
| GET `/vocab`, POST `/vocab`, PATCH `/vocab/{id}` | terms per field | read any, write admin |
| GET `/items` | filters: status[], priority[], group[], category[], owner_org[], assignee, kind, due_before/after, q; sort; page/limit | any |
| POST `/items`, GET `/items/{id}`, PATCH `/items/{id}` | CRUD; PATCH is partial and is how the board changes status | any |
| DELETE `/items/{id}`, POST `/items/{id}/restore` | soft delete / restore | any / admin |
| GET/POST `/items/{id}/updates`, PATCH/DELETE `/items/{id}/updates/{uid}` | timeline | any (edit own) |
| GET `/items/{id}/history` | audit events for the item and its updates | any |
| GET `/activity` | recent audit events; filters: org, actor, entity_type, since | any |
| GET `/dashboard/summary` | see §10 | any |
| POST `/import/excel/preview`, POST `/import/excel/commit` | see §9 | admin |
| GET `/export/excel` | current items as xlsx; same filters as `/items` | any |

## 8. Vocabularies and normalization

Seeded `group` terms for GS098: `General Issues`, `Gen1 (existing) CMC`,
`Gen2 (Process 2.0) CMC`.

Seeded `category` terms: `QA`, `QC`, `AS`, `AS/QC`, `DS`, `DP`, `USPD`,
`Legal`, `Non-clinical`. Admins can add, rename, reorder, and deactivate
terms. Renaming a term rewrites the value on existing items in one audited
operation.

Owner mapping (case- and whitespace-insensitive):
`gensci` → `gensci`; `yarrow` → `yarrow`; `gensci/yarrow`, `yarrow/gensci`
→ `joint`. Anything else is unmapped (see §9).

## 9. Excel import and export

### Import flow

1. Admin uploads the xlsx (UI) or runs `cli import-excel path` (CLI).
2. Server parses the sheet named `Action Item`, requiring the 13 known
   headers in row 1 (extra columns are ignored; missing ones fail fast).
3. Server returns a **preview**: normalized rows, counts, warnings, and a
   list of **unmapped values** per field (group, category, owner, status).
4. Admin supplies `overrides` mapping unmapped raw values to canonical ones
   (or new vocab terms), then calls **commit**. Commit re-runs normalization
   with the overrides and inserts everything in one transaction; any
   remaining unmapped value, duplicate `entry_no` within the file, or
   `entry_no` already present in the program aborts the whole import. This
   makes the import safe to run again with a file containing only new rows,
   and impossible to run twice with the same rows.
5. One `audit_event(entity_type=import)` records counts and the file name.

### Normalization rules

| Sheet column | Rule |
|---|---|
| Entry No. | integer; duplicates or blanks abort |
| Date | `YYYY/MM/DD ~ YYYY/MM/DD` → `raised_on` = first date, `source` = `Meeting <first> to <second>`; Excel serial or datetime → `raised_on`; unparsable → `raised_on` = import date + warning |
| Group | fold full-width parentheses to ASCII, collapse whitespace, case-insensitive match to seeded terms |
| Action Item | `title` (first line, truncated at 500 with warning); remaining lines → `details` |
| Translation in Mandarin | kept only in `provenance` |
| owner | mapping in §8 |
| CMC Category | trim; `NA`/blank → null; otherwise match a category term or flag as unmapped |
| status | `Completed` → `completed`; `In Progress` → `in_progress`; `NA` → `kind = note`, status null; blank → `open` + warning |
| Notes/Risks | text matching `this is a note` (case-insensitive) also forces `kind = note`; `NA` → empty |
| Checkpoint/DDL | serial/datetime → `due_on`; `NA`/blank → null |
| Priority | `P1`/`P2`/`P3` → `p1`/`p2`/`p3`; `NA`/blank → null |
| Status Updates | split on `UPDATE-(\d{8}):?` markers into `item_update` rows dated from the marker; text before the first marker (or text without markers) becomes one update dated `raised_on`; `NA`/blank → none; author = importing admin |
| file path | strip surrounding quotes |
| Every row | full raw row stored in `provenance` |

### Export

`GET /export/excel` produces a workbook with one sheet `Action Item` and
columns in the original order minus the translation column, plus
`Last Updated` and `Updated By`:

`Entry No.`, `Date`, `Group`, `Action Item`, `Owner`, `CMC Category`,
`Status`, `Checkpoint/DDL`, `Priority`, `Status Updates`, `Notes/Risks`,
`File Path`, `Last Updated`, `Updated By`.

`Action Item` = title, then a blank line and details when present. `Owner`
renders `GenSci`, `Yarrow`, or `GenSci/Yarrow`. `Status` renders labels
(`Note` for notes). `Status Updates` joins timeline entries as
`UPDATE-YYYYMMDD: body` lines, oldest first.

## 10. Frontend

### Screens

1. **Login** and **Accept invitation** (same page for reset links).
2. **Dashboard** (default after login).
3. **Items** with a Table/Board toggle that persists per browser.
   - Table: sortable columns, filter bar (status, priority, group, category,
     owner, assignee, kind, due range), free-text search, column visibility
     chooser, URL-synced filters so views can be shared by link.
   - Board: one column per status (notes excluded); `completed` and
     `cancelled` columns start collapsed and expand on click. Cards show entry no,
     title, priority, owner org, due date, and a stale marker. Dragging a
     card calls `PATCH /items/{id}` with the new status; optimistic update
     with rollback on error. Cards order by priority then due date.
4. **Item detail** as a right-side sheet over the list, with a full-page
   route for deep links: editable fields, update timeline with a compose
   box, and a History tab rendering audit diffs.
5. **Admin**: Users & invitations (create invite → copyable link), Vocab,
   Import (upload → preview with warnings and unmapped-value pickers →
   commit), Export.

### Dashboard summary (`GET /dashboard/summary`)

- Definitions: an item is **open** when `kind = action` and status is not
  `completed` or `cancelled`; **overdue** when open and `due_on` is before
  today; **due soon** when open and `due_on` falls within `DUE_SOON_DAYS`.
- Tiles: open items by status, open P1 count, overdue count, due soon count.
- Needs attention: overdue; due soon; `in_progress`/`blocked` items with no
  update in `STALE_DAYS` (14). Each row links to the item.
- Recent activity: last 20 audit events with actor, org badge, summary, and
  relative time; filter by org; "load more" pages through `/activity`.
- Breakdowns: open items by group and by owner org.

### Visual direction

Clean data-product aesthetic: neutral surfaces, one accent color, strong
typographic hierarchy, generous row height in the table, and semantic
colors reserved for status and priority so they carry meaning. Light and
dark themes via CSS variables. Implementation will follow the
`frontend-design` skill when the frontend is built; this spec fixes only the
constraints above.

### State and data

TanStack Query for server state with query keys per resource; forms via
react-hook-form + zod mirroring backend schemas; all state updates
immutable. A generated TypeScript client from the FastAPI OpenAPI schema
keeps DTOs in sync.

## 11. Error handling and validation

- Pydantic validates every request body and query; violations return 422
  with the envelope's `fields` map.
- Domain errors (`not_found`, `forbidden`, `conflict`, `invalid_transition`)
  are typed exceptions mapped to 404/403/409/422 by one handler.
- Unexpected exceptions are logged with a request id and stack trace and
  return a generic 500 message; the request id is echoed in the response so
  users can report it.
- Frontend: field-level errors inline, toasts for operation results, a
  global error boundary, and session-expiry redirect to login.
- Import commit is all-or-nothing.

## 12. Security

- argon2id password hashing; minimum 10-character passwords.
- Session cookie: `HttpOnly`, `SameSite=Lax`, `Secure` when served over
  HTTPS; sliding expiry; logout revokes server-side.
- CSRF: `SameSite=Lax` + required `X-Requested-With` header on mutations.
- Login rate limit: 5 attempts per minute per email and per IP.
- Invitation/reset tokens: 32 random bytes, stored hashed, single use,
  time-limited.
- `SECRET_KEY` is required at startup; the app refuses to boot without it.
  `ADMIN_PASSWORD` is read only when no users exist and is never logged.
  No secrets in the repo; `.env.example` documents every variable.
- CORS allowed only for the Vite dev origin in development.

Configuration (`.env`):

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | required | session signing |
| `DATABASE_URL` | `sqlite:////data/app.db` | switch to Postgres with the `postgres` profile |
| `APP_ORIGIN` | `http://localhost:8000` | used for invitation links and CORS |
| `APP_PORT` | `8000` | host port mapped by compose |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | none | first admin, created only when no users exist |
| `INITIAL_IMPORT_PATH` | none | mounted xlsx imported once when the program has no items |
| `DOMAIN` | none | `proxy` profile only; Caddy obtains certificates for it |
| `SESSION_TTL_HOURS` | `72` | |
| `INVITE_TTL_DAYS` | `7` | |
| `DUE_SOON_DAYS`, `STALE_DAYS` | `14` | dashboard thresholds |
| `LOG_LEVEL` | `info` | |

## 13. Testing

- **Backend unit**: normalization functions, permission checks, audit diff
  builder, dashboard calculations.
- **Backend API**: httpx client against a temporary SQLite database; every
  endpoint has at least a happy path, an auth failure, and a validation
  failure test. Importer tests use a copy of the real spreadsheet as a
  fixture and assert the expected counts (57 items, 5 notes, mapped groups,
  parsed update timelines).
- **Frontend**: Vitest + Testing Library for table filters, board drag
  status change, item form validation, and dashboard rendering from a
  mocked summary.
- **E2E**: Playwright: seed admin → invite member → accept → member logs in
  → creates item → posts update → drags card to In progress → dashboard
  shows the activity.
- **Container smoke test**: build the image, `docker compose up -d` with a
  throwaway `.env`, wait for the health check, log in as the seeded admin,
  and confirm the initial import produced 57 items. Runs in CI on every push.
- Coverage gate: 80% on backend; frontend measured but not gated in v1.

## 14. Phasing

1. **Backend core, shipped in a container** — project scaffold, Dockerfile,
   compose file, self-configuring entrypoint, health endpoint, config,
   models, migrations, auth, users/invitations, items, updates, vocab,
   audit, dashboard summary, CLI import, tests. Deliverable:
   `docker compose up -d` yields a working API with the spreadsheet imported.
2. **Frontend core** — app shell, login/accept, items table, item detail,
   timeline, history, built into the same image. Deliverable: both teams can
   use it from one container.
3. **Board, dashboard, admin** — Kanban, dashboard, users/invites/vocab
   screens, import/export UI, generated API client, frontend tests.
4. **Release hardening** — CI workflow (tests, container smoke test, image
   publish on tag), Playwright e2e, `postgres` and `proxy` profiles verified,
   deployment note with the registry and tarball paths.

Each phase gets its own implementation plan.
