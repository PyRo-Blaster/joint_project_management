# MCP Phase 1 Development Log

Branch: `claude/optimistic-davinci-wpxhpl`. Started 2026-09-21.
Plan: `docs/superpowers/plans/2026-09-21-mcp-phase1-api-tokens.md`.
Design: `docs/superpowers/specs/2026-09-19-mcp-agent-access-design.md`.

Records decisions, deviations, and the two bugs the test suite could not see.

## Environment

- uv 0.8.17; backend tests on **Python 3.13.12** (`uv run --python 3.13 pytest`).
  The pinned 3.14 still resolves to a pydantic-breaking release candidate, as
  the Phase 2 and Phase 4 logs recorded.
- node v22.22.2 for the frontend. No Docker daemon in the sandbox, so the
  container smoke test was replaced by a direct CLI run against a real migrated
  SQLite database (see "Two bugs" below) — which is what caught both defects.
- Baseline before starting: 108 backend tests, 36 frontend tests.

## Planned deviations from the design (all deliberate)

1. **`via` is `web`, `mcp`, `cli`.** The design also listed `import`. `via`
   describes how a request arrived, which is orthogonal to what it did, and an
   import is already identifiable by `entity_type = "import"`. A value nothing
   sets is worse than no value.
2. **`scopes` and `write_mode` no longer overlap.** The design had a `read_only`
   write mode, which says the same thing as "no `write` scope". So `scopes` is
   `read` or `read,write`, and `write_mode` is `append` or `interactive`,
   meaningful only when `write` is present. `write_mode` is stored now and read
   in Phase 3, when edit tools exist.
3. **Token management is cookie-only.** A write-scoped token could otherwise
   mint itself a non-expiring successor. Enforced by a `SessionUser` dependency
   that rejects bearer credentials; `test_a_bearer_token_cannot_manage_tokens`
   covers it.
4. **Self-service lives at `/tokens`, not on a profile page.** The design put it
   on a profile page that does not exist yet; inventing one belongs with the
   V2.0 bilingual work. The page shows a member their own tokens and gives
   admins a toggle for everyone's.

## Implementation note: attribution without touching every service

The interesting problem was getting "this arrived over MCP, on Alice's token"
from the HTTP layer down to `record_event`, which lives three layers below.

- **Rejected: contextvars.** FastAPI runs sync dependencies in a threadpool via
  `anyio.to_thread.run_sync`, which copies the context into the worker. A value
  set inside a dependency does not propagate back to the endpoint, so this
  would have failed silently and intermittently.
- **Rejected: a parameter on every service.** Correct but invasive — roughly
  fifteen call sites and every service signature, for one piece of metadata.
- **Chosen: `Session.info`.** The SQLAlchemy session is already threaded through
  every service call by construction, so it is the natural carrier.
  `app/services/principal.py` sets and reads a frozen `Principal` on it, the
  auth dependency stamps it, `session_scope` stamps `cli`, and `record_event`
  reads it. **No service signature changed.**

## Two bugs the test suite could not see

Both were found by running the CLI against a real migrated database, and both
came from the same root cause: **the tests never exercise the real startup path
or the real schema.**

1. **`python -m app.cli token …` reported "No such command".** The token
   sub-app was appended to `cli.py` after the `if __name__ == "__main__"` guard,
   so `cli()` ran before `add_typer` did. Every unit test imports the module,
   which runs all top-level code, so all eight CLI tests passed against a
   command that did not exist when invoked for real. Fixed by moving the block
   above the guard.

2. **Creating a token failed with `CHECK constraint failed:
   ck_audit_event_entity_type_in`.** Migration 0001 pinned `entity_type` to a
   list predating `api_token`. The suite builds its schema with
   `Base.metadata.create_all` from the models, which has the new list, so no
   test saw the stale constraint — and `alembic check` reported "no new upgrade
   operations" because autogenerate does not detect CHECK constraint drift.
   Migration 0002 now rebuilds that constraint. `downgrade` deletes the orphaned
   `api_token` audit rows first, since dropping the table leaves them describing
   an entity that no longer exists and the restored 0001 constraint would reject
   them.

   **Follow-up worth doing:** two tests now write through the *migrated* schema
   rather than `create_all`. That gap is generic, not specific to this change —
   any future CHECK constraint edit will hide the same way. Consider running a
   slice of the API suite against a migrated database in CI.

## Result

| | Before | After |
|---|---|---|
| Backend tests | 108 | 164 |
| Backend coverage | 92% | 92.6% (gate 80%) |
| Frontend tests | 36 | 39 |

Green: `ruff check`, `ruff format --check`, `alembic check`, `npm run
typecheck`, `npm run lint`, `npm run build`. The CLI was exercised end to end
against a migrated SQLite database: bootstrap, create, list, revoke, and a
`0002 → 0001 → head` round trip.

## What Phase 1 delivers on its own

The REST API now takes a bearer credential, so a script can use it without a
browser, and every write records whether a person or an agent made it. No MCP
server exists yet — that is Phase 2 (read-only tools) and Phase 3 (writes).

## Open items for Phase 2

- `write_mode` is stored but not yet enforced; it gates the edit tools in Phase 3.
- Rate limiting per token is not implemented. The design puts it with the MCP
  server, and the in-memory limiter still needs moving to the database for
  multi-worker safety (already on the V2.0 quality plan).
- The `via` filter on the audit log page is a V2.0 phase 1 item; the column it
  needs now exists.
