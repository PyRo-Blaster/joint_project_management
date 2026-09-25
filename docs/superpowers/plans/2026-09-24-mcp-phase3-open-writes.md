# MCP Phase 3: Open Writes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Agents can post dated updates and file new items unattended, every write attributed to the token that made it, with duplicates refused and agent-created items flagged until a person reviews them.

**Spec:** design §6.2 (open tools), §7.5–7.8 (open creates, guardrails), §8 (errors, `weekly_update` prompt), §9 (data model, config), §10 task 3, §13 acceptance.

**Format note.** Phases 1 and 2 used full-code plans. From here the plans list decisions, files and tests, and the code lands in the task's commit. The patterns are established; duplicating every function into the plan doubled the work without adding review value.

---

## Decisions (and one Phase 1 flaw)

1. **Phase 1 flaw, fixed here: bearer tokens become read-only on the REST API.**
   Phase 1 let a write-scoped token call `POST/PATCH/DELETE /api/items` directly,
   which bypasses every MCP guardrail: an agent could soft-delete an item or
   rewrite its title and owner, both of which the design says are impossible.
   All agent writes now go through `/mcp`. A token on a mutating REST request
   gets 403 naming `/mcp`.
2. **Review state is derived, not stored twice.** §9 specifies
   `agent_ack_at`/`agent_ack_by` on the item. "An agent touched it" is read from
   `audit_event` (`via='mcp'`, action `created`/`updated`/`status_changed`),
   the same way `last_update_dates` already works. An item needs review when its
   latest agent touch is after `agent_ack_at`. No `agent_touched_at` column.
3. **What flags an item.** Agent-created items (§7.7) and, from Phase 4, agent
   edits (§7.4). Agent-posted *updates* do not flag the item (§7.6 lists them
   as "direct"), otherwise every weekly update would need a click.
4. **Acknowledging is a human act.** `POST /api/items/{id}/ack` rejects bearer
   tokens, so an agent cannot mark its own work reviewed. It is audited with a
   new action `acknowledged`, which means migration 0003 rebuilds the
   `audit_event.action` CHECK constraint (Phase 1's lesson).
5. **A person editing the item acknowledges it implicitly** (§7.4), done in
   `patch_item` when the principal is not `mcp`. Opening the item does **not**
   acknowledge it — deviation from §7.7's "until a person opens them": a glance
   is not a review, and the Phase 4 undo bar lives on the same surface and must
   not vanish when the sheet opens. Acknowledging is one click.
6. **Idempotency.** `(program_id, idempotency_key)` is unique. A repeat within
   `IDEMPOTENCY_TTL_HOURS` returns the original item and files nothing. A repeat
   after the window is refused with a message naming the original entry,
   because the unique constraint cannot allow a second row.
7. **Duplicate check** lives in `services/items.find_similar_items` so the UI
   can use it later; the MCP tool calls it. Normalised title similarity
   (`difflib`) ≥ 0.82 against non-deleted items refuses without `confirm_new`.
8. **Kill switch and scope.** Write tools require `write` scope and
   `MCP_WRITES_ENABLED=true`; both refusals use the §8 wording. Both write
   modes (`append`, `interactive`) may use the open tools.

## Files

- `backend/alembic/versions/0003_idempotency_and_agent_review.py` — new columns, unique constraint, action CHECK rebuild
- `backend/app/constants.py`, `app/config.py` — `acknowledged`; `mcp_writes_enabled`, `idempotency_ttl_hours`
- `backend/app/models/action_item.py` — `idempotency_key`, `agent_ack_at`, `agent_ack_by`
- `backend/app/services/agent_review.py` — derive pending review, acknowledge
- `backend/app/services/items.py` — idempotency on create, implicit ack on human patch, `find_similar_items`
- `backend/app/api/deps.py` — bearer tokens read-only on REST
- `backend/app/api/items.py` — `POST /items/{id}/ack`; `needs_agent_review` on item output
- `backend/app/schemas/{items,audit,dashboard}.py` — review flag, `via`/`token_name`, unreviewed list
- `backend/app/services/dashboard.py` — `agent_unreviewed`
- `backend/app/mcp/tools_write.py` — `cmc_post_update`, `cmc_create_item`
- `backend/app/mcp/prompts.py` — `weekly_update`
- `frontend/…` — agent chip in History and the activity feed, unreviewed chip on table rows and board cards, a review bar with "Looks right" on the item, the dashboard list

## Tasks

- [ ] REST read-only for tokens (test first, update the Phase 1 test that asserted the flaw)
- [ ] Migration 0003 + model + constants, with a migration test writing `acknowledged` through the migrated schema
- [ ] `agent_review` service + implicit ack + ack endpoint (unit + API tests)
- [ ] Idempotency and duplicate finder in the item service (unit tests)
- [ ] `cmc_post_update`, `cmc_create_item`, scope and kill switch, `weekly_update` prompt (MCP tests)
- [ ] API output: `via`/`token_name` on audit events, `needs_agent_review` on items, dashboard list; regenerate OpenAPI types
- [ ] Frontend chips, bar, dashboard list (Vitest)
- [ ] Extend `scripts/mcp_smoke.py`, run it live, write the dev log, check §6.2/§7.7/§7.8/§13 line by line
