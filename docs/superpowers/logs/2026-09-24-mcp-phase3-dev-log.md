# MCP Phase 3 Development Log — Open Writes

Branch: `claude/optimistic-davinci-wpxhpl`. 2026-09-24.
Plan: `docs/superpowers/plans/2026-09-24-mcp-phase3-open-writes.md`.
Design: `docs/superpowers/specs/2026-09-19-mcp-agent-access-design.md`.

Agents can now post dated updates and file items unattended. Every write is
attributed to the token that made it, near-duplicates are refused, and an
agent-filed item stays flagged until a person confirms it.

## Issues found and fixed (flagged)

1. **Security: the REST API let write tokens bypass every MCP guardrail.**
   Phase 1 allowed a `write`-scoped token to `POST`, `PATCH` and `DELETE`
   under `/api`, so an agent could soft-delete an item or rewrite its title
   and owner — both things the design says no token can ever do. A Phase 1
   test even asserted the behaviour. Now every token is read-only on the REST
   API and all agent writes go through `/mcp`. Two tests assert the opposite
   of the old one, including that `DELETE` and a title `PATCH` are refused and
   leave the item untouched, and the live smoke test checks it over HTTP.
2. **Phase 1 gap: `MCP_DEFAULT_WRITE_MODE` (§9) was hard-coded.** Now a setting,
   used by the API and the CLI when no mode is chosen.
3. **Robustness: two kinds of error escaped as crashes or as nothing.** A
   pydantic `ValidationError` (a 600-character title) surfaced as "Error
   executing tool", and a domain error with per-field detail lost the detail
   ("Invalid input"). Both now map to a message naming the field.
4. **Process slip:** one commit landed with three line-length lint errors
   because a command chain used `;` instead of `&&`. Fixed in the next commit;
   CI never saw it because it was not pushed in between.

## Deviations from the design (deliberate)

| Design | Built | Why |
|---|---|---|
| §7.7: an agent-filed item is unreviewed "until a person opens it" | Until a person clicks *Looks right* or edits the item | A glance is not a review, and Phase 4's undo bar lives on the same surface and must not vanish when the sheet opens |
| §9: `agent_ack_at`/`agent_ack_by` only | Same, and "an agent touched it" is derived from `audit_event` (`via='mcp'`, created/updated/status_changed) | One source of truth per fact; no `agent_touched_at` column to keep in sync |
| §8 missing-scope copy: "An admin can issue a new token in Admin › API tokens" | "Create a token with write access under API tokens in the web app" | Phase 1 made tokens self-service at `/tokens` |
| §9 IDEMPOTENCY_TTL: a repeat within 24 h returns the original | Same; a repeat *after* the window is refused naming the original | The per-programme unique constraint cannot allow a second row with the same key |
| §5/§7.8: "the Audit log answers what the agents changed in one filter" | The source is stored and shown, filterable in `cmc_list_activity`; **the Audit log page does not exist yet** | It is a V2.0 phase 1 deliverable, not built. The column it needs is ready |

Also decided, consistent with the design's intent: agent-posted *updates* do
not flag an item (§7.6 lists them as direct; flagging would make every weekly
update a chore), and `POST /items/{id}/ack` refuses bearer tokens so an agent
cannot mark its own work reviewed.

## Line-by-line check against the spec

| Spec | Status |
|---|---|
| §6.2 `cmc_post_update`: `entry_no`, `body`, `occurred_on` default today, `dry_run` | Done |
| §6.2 `cmc_create_item`: all fields, `kind`, `idempotency_key`, `confirm_new`, `dry_run`, duplicate check | Done |
| §6.2 annotations: not read-only, not destructive, not idempotent | Done |
| §7.7 duplicates refused naming the candidate; `confirm_new` overrides | Done |
| §7.7 review-after chip and dashboard list | Done (deviation on "opens", above) |
| §7.8.1 `dry_run` · .2 idempotency · .3 rate limits · .4 annotations · .5 attribution | Done (rate limit in-memory, per Phase 2 addendum) |
| §8 errors: unknown entry, invalid status with hint, unknown group, note with status, missing scope | Done. Stale write is Phase 4 |
| §8 `weekly_update` prompt | Done |
| §9 config: `MCP_WRITES_ENABLED`, `IDEMPOTENCY_TTL_HOURS`, `MCP_DEFAULT_WRITE_MODE`, rate limits | Done |
| §9 `idempotency_key` unique per programme, `agent_ack_at`, `agent_ack_by`; `POST /items/{id}/ack` | Done, migration 0003 |
| §13 open path: search, read, post; History marks it "via agent" with the token name | Done, UI tested |
| §13 create: unreviewed chip, dashboard list, duplicate refused without `confirm_new` | Done |
| §13 read token refused on every write; kill switch stops writes, reads keep working | Done |
| §13 no tool for delete, restore, users, vocabulary, import | Done, asserted in tests and live |

## Result

| | Before Phase 3 | After |
|---|---|---|
| Backend tests | 212 | 262 |
| Frontend tests | 39 | 44 |
| Live smoke checks | 17 | 29 |

Green: `ruff check`, `ruff format --check`, `alembic check`, the backend and
frontend suites, `npm run typecheck`, `npm run lint` (0 errors, 6 warnings that
predate this work), `npm run build`, and `scripts/mcp-smoke.sh`.
