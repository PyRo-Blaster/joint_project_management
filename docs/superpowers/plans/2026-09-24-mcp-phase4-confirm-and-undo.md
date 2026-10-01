# MCP Phase 4: Edits with Confirm and Undo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** An agent in conversation with a person can change an item's live state: it previews the exact diff, the person agrees, and it confirms. Every agent change is then flagged on the item and one click to undo for 14 days. Undo works on a person's changes too.

**Spec:** design §6.2 (confirm tools), §7.2–7.6, §8 (stale-write copy, `meeting_minutes_to_changes`), §9 (`reverted_by_event_id`, revert endpoint, `MCP_CONFIRM_TTL_MINUTES`, `AGENT_UNDO_DAYS`), §10 task 4, §13.

---

## Decisions

1. **The confirm token carries no patch.** It is `ct_` + a signed envelope
   holding when it was issued and when it expires. The signature is an HMAC
   (`SECRET_KEY`) over the tool, the calling token's id, the canonical JSON of
   the requested change, the issue time and the expiry. On the confirming call
   the server recomputes it from the call's own arguments, so:
   - a changed argument ⇒ the signature fails ⇒ "does not match these arguments";
   - another agent's token ⇒ the signature fails (bound to the caller's token id);
   - an item edited since the preview ⇒ its `updated_at` is later than the issue
     time ⇒ the §8 stale-write message naming who changed what.
   Nothing is stored. This is how the design's "HMAC over the item id, the
   canonical patch, and the base `updated_at`" is realised; detecting staleness
   by issue time rather than by signing each base value lets one token cover a
   batch of any size.
2. **`patch_item` and `create_update` gain `commit=True`.** With `commit=False`
   they flush instead, so `cmc_set_status` with a note and `cmc_apply_batch`
   commit once: all of it lands, or none.
3. **Undo is its own service, `revert_event`, recording action `reverted`.** The
   spec asks both for "the normal service call" and for a `reverted` event;
   `patch_item` records `updated`/`status_changed`, so undo reuses the item
   service's validators and diff but records its own action. It is still the
   service layer doing the write.
4. **Undo refuses to clobber later work.** A field can be reverted only if its
   current value is still the event's `new` value. Otherwise the refusal names
   the field and says to undo the later change first. All fields or none.
5. **What can be undone:** item `updated` and `status_changed` events, not yet
   reverted, within `AGENT_UNDO_DAYS` — for people's changes as well as agents'
   (the design notes undo is "independently useful for human mistakes"). The
   window applies to both, so the name `AGENT_UNDO_DAYS` is kept for the spec's
   sake. Creates, deletes, restores and updates on the timeline are not undone.
6. **Clearing a value** through `cmc_update_item`: an empty string clears a date
   or text field, and `assignee_id=0` unassigns. Clearing is an edit like any
   other and needs the confirm step.
7. **`cmc_apply_batch`** takes up to 50 changes, each an entry number plus any
   of the editable fields, a `status`, and an optional `post` (a timeline note).
   A batch with any field change needs the interactive write mode; a batch of
   posts alone is additive and needs only `write`. An entry may appear once.

## Files

- `alembic/versions/0004_revert.py` — `audit_event.reverted_by_event_id`, `reverted` in the action CHECK
- `app/services/revert.py`, `app/api/activity.py` (`POST /activity/{id}/revert`)
- `app/services/items.py`, `app/services/updates.py` — `commit=` parameter
- `app/mcp/confirm.py` — issue and verify confirm tokens
- `app/mcp/tools_edit.py` — `cmc_set_status`, `cmc_update_item`, `cmc_apply_batch`
- `app/mcp/prompts.py` — `meeting_minutes_to_changes`
- `app/mcp/render.py` — mark undone changes in history
- frontend: change bar with Undo and Looks right, Undo on History rows, dashboard tile linking to the filtered items list

## Tasks

- [ ] Migration 0004, model, constants, config — migration tests through the migrated schema
- [ ] `commit=` on `patch_item` and `create_update`
- [ ] `revert_event` + endpoint + `reverted_by_event_id` on audit output
- [ ] Confirm tokens (unit: round trip, tamper, other caller, expiry, stale)
- [ ] `cmc_set_status`, `cmc_update_item`, `cmc_apply_batch` (MCP tests incl. append mode refused, identity fields absent, stale write copy, batch atomicity)
- [ ] `meeting_minutes_to_changes` prompt
- [ ] Frontend bar, History undo, dashboard tile, items filter
- [ ] Live smoke, dev log, line-by-line spec check
