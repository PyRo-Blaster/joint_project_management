# MCP Phase 4 Development Log — Edits with Confirm and Undo

Branch: `claude/optimistic-davinci-wpxhpl`. 2026-09-24.
Plan: `docs/superpowers/plans/2026-09-24-mcp-phase4-confirm-and-undo.md`.

An agent can now change an item's live state after the person it is working
with sees and approves the exact diff, and anyone can undo a change for 14 days.

## Issue found and fixed (flagged)

**The MCP SDK silently drops arguments a tool does not take.** Verified
directly: a tool called with an extra argument runs normally and reports
success. Consequences before the fix:

- `cmc_update_item(title="…")` would report success without renaming anything,
  so an agent would tell its user the item was renamed;
- a typo such as `prority="p1"` on `cmc_create_item` would file the item without
  its priority and report success.

The spec's acceptance line "attempting [an identity field] is a schema error
naming the web UI" was therefore not achievable by leaving the parameter out.
A server middleware (`app/mcp/strict_args.py`) now sees the raw `tools/call`
arguments before validation and refuses anything the tool's schema does not
list, for **every** tool: identity fields get a message pointing to the web app,
other unknown names get the valid list and a did-you-mean. Batch entries are
checked the same way. Tested in the suite and live.

## Deviations from the design (deliberate)

| Design | Built | Why |
|---|---|---|
| §7.3: the token signs "the item's `updated_at` at step 1" | It signs the issue time; stale = a field-change event on the item after it | `updated_at` also moves when someone posts a timeline note, which would reject a confirm for a change nobody made. Issue time also lets one token cover a batch of any size |
| §7.3 wording `Confirm with confirm="ct_…" (valid 10 minutes)` | "call cmc_update_item again with the same arguments and confirm="ct_…" (valid until 14:12 UTC)" | Tells the agent the arguments must match, and gives a clock time |
| §7.4 "applying it through the normal service call" and "action `reverted`" | `revert_event`, a service reusing the item validators and diff, records `reverted` | `patch_item` records `updated`/`status_changed`; the spec asks for both, and a dedicated service still keeps every write in the service layer |
| §7.4 undo "for 14 days" for agent changes | For any change, a person's or an agent's; refused if a field changed again since | The design calls undo "independently useful for human mistakes"; refusing when a field has moved on stops undo clobbering later work |
| §7.4 dashboard "4 agent changes awaiting your eye" tile | A notice above the tiles, shown only when the count is above zero, linking to the filtered list | A seventh tile leaves an orphan in the grid, and a standing zero is noise |
| §6.2 `cmc_set_status` note "in the same transaction" | Kept, by giving `patch_item` and `create_update` a `commit=False` option | Needed anyway so a batch lands all or none |

Unchanged decisions carried from Phase 3: opening an item does not acknowledge
it, and tokens cannot acknowledge or undo (both are person-only REST actions).

## Line-by-line check against the spec

| Spec | Status |
|---|---|
| §6.2 `cmc_set_status` (`entry_no`, `status`, `note`, `confirm`; idempotent) | Done |
| §6.2 `cmc_update_item` over the §7.2 fields only; empty clears, `assignee_id=0` unassigns | Done |
| §6.2 `cmc_apply_batch`: one preview, one token, all or none | Done; max 50, one entry per item |
| §7.2 identity fields never agent-editable | Done, and enforced against the SDK dropping them |
| §7.3 stateless token: tamper, other caller, expiry, staleness | Done (staleness by event, above) |
| §7.4 bar with diff, time, token, Undo, Looks right; implicit ack on human edit | Done |
| §7.4 undo recorded as `reverted`, linked from the original | Done, migration 0004 |
| §7.5 append mode cannot edit | Done; a batch of posts alone is additive and allowed |
| §8 stale-write copy names time, person, field → value, and `cmc_get_item` | Done |
| §8 `meeting_minutes_to_changes` prompt | Done |
| §9 `reverted_by_event_id`, `POST /activity/{id}/revert`, `MCP_CONFIRM_TTL_MINUTES`, `AGENT_UNDO_DAYS` | Done |
| §13 confirm path, stale confirm, undo path, identity refusal, append refusal, batch | Done, in the suite and live |

## Result

| | Before Phase 4 | After |
|---|---|---|
| Backend tests | 262 | 309 |
| Frontend tests | 44 | 49 |
| Live smoke checks | 29 | 41 |

The live run includes a real undo: an agent's confirmed status change is
reverted through a person's cookie session and the status comes back.
