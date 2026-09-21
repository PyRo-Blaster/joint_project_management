# Agent Access via MCP — Design

Date: 2026-09-19
Status: Draft for user review
Extends `2026-09-06-joint-cmc-tracker-design.md` (v1) and the three
`2026-09-16-v2-*` documents. Target release: **V2.1**, with two small
pieces pulled into V2.0 (§9).
Program: GS098 (GenSci × Yarrow).

## 1. Problem

Every write to the tracker goes through the web UI today. An agent asked to
"post this week's DP update on entry 42" has to drive a browser: log in,
find the row, open the sheet, type, save. That is slow, brittle, and
unauditable in any useful way — the audit trail says a person did it.

An MCP server makes the tracker a first-class tool surface. The agent calls
`cmc_post_update(entry_no=42, body="…")`, the change lands through the same
service layer as the UI, and the audit row says *who* authorised it and
*that it came from an agent*.

## 2. Decisions

| Topic | Decision | Why |
|---|---|---|
| Transport | **Streamable HTTP mounted at `/mcp`** in the existing FastAPI container | No new image, no new port, no second thing to deploy. TLS, health check, and backups already cover it. Matches the project's "one image, one command" rule. |
| stdio clients | Documented bridge (`mcp-remote`), **not** a second implementation | One code path. A stdio-only client on a laptop runs the bridge; everything else connects to the URL directly. |
| Where tools call | **The service layer, in-process** | Services are the real contract: they own writes and record the audit event in the same transaction. Routers and MCP tools become two adapters over one core. No HTTP round-trip to ourselves. |
| Language | Python, official `mcp` SDK (FastMCP), in `backend/app/mcp/` | Same container, same dependency tree, same tests. A Node process in this image would break the single-process model. |
| Auth | **Bearer API tokens** scoped to a user, new `api_token` table | Session cookies are for browsers. An agent needs a long-lived, revocable, scoped credential that is not a password. |
| Identity | Every token belongs to a **real user**; the agent acts as that person | Keeps the permission model, the audit trail, and accountability unchanged. No "robot" accounts with ambiguous ownership. |
| Write boundary | **Append applies, overwrite proposes, delete does not exist** (§7) | Creating an item and posting an update add information and destroy none, so they run unattended. Changing a field overwrites what a person wrote, so a person confirms it. Deleting has no tool at all. |
| Destructive tools | **No tool exists** — no delete, no restore, no user admin, no vocabulary, no import | An absent door beats a guarded one. These stay in the web UI. |
| Item handle | Tools take **`entry_no`** (the number both teams already say out loud), return both `entry_no` and `id` | "#42" is the shared vocabulary; the internal id is an implementation detail. |

## 3. Architecture

```
                    ┌─────────────────────────────────────────┐
   Claude Code  ──► │  app container (unchanged image shape)  │
   claude.ai    ──► │                                         │
   Claude Desktop   │   /mcp   ──►  app/mcp/  (FastMCP)       │
       │            │                   │                     │
       │ stdio      │   /api/* ──►  app/api/ (routers)        │
       └─ mcp-remote│                   │                     │
                    │                   ▼                     │
                    │            app/services/  ◄── the only  │
                    │              (audit in the same txn)    │
                    │                   ▼                     │
                    │            SQLite / PostgreSQL          │
                    └─────────────────────────────────────────┘
```

`app/mcp/` is a sibling of `app/api/`, not a layer on top of it. Both are
thin adapters: they validate input, call a service, and shape the result
for their protocol. The invariant from the flow map holds unchanged —
**nothing writes the database except a service, and every service write
records its audit event in the same transaction.**

Mounting: `create_app()` mounts the FastMCP ASGI app at `/mcp` when
`MCP_ENABLED` is true (default true). The SPA fallback already refuses to
swallow non-SPA prefixes; `/mcp` joins `/api` in that list.

## 4. Authentication and authorisation

### 4.1 API tokens

New table `api_token`:

| Field | Type | Notes |
|---|---|---|
| `id` | int | |
| `user_id` | FK user | the person the agent acts as |
| `name` | str | "Claude Code — Alice laptop"; shown in the UI and the audit trail |
| `token_hash` | str, unique | SHA-256 of the raw token, hashed at rest, same as sessions |
| `prefix` | str(8) | first 8 chars, shown in listings so a token is identifiable without revealing it |
| `scopes` | str | comma-separated: `read`, `write` |
| `expires_at` | datetime, nullable | default `MCP_TOKEN_TTL_DAYS` (90); null means no expiry, admin-only |
| `last_used_at` | datetime, nullable | |
| `created_by` | FK user | |
| `revoked_at` | datetime, nullable | revocation is immediate and permanent |

Raw token format `cmct_<43 url-safe chars>`, generated with
`secrets.token_urlsafe(32)` — the same generator the session and invitation
tokens already use. Shown **once** at creation, never retrievable again.

### 4.2 Scopes

| Scope | Grants |
|---|---|
| `read` | every read tool |
| `write` | the write tools, subject to the token's write mode (§7.4) — `append` applies directly, `propose` creates proposals a person approves |

`admin` is deliberately **not** a scope. Admin capabilities (users, vocab,
import, restore) have no MCP tools, so no token can reach them. A member's
token cannot exceed the member's own permissions either: the scope narrows,
it never widens. A deactivated user's tokens stop working immediately,
because resolution re-checks `is_active` exactly as session resolution does.

### 4.3 Resolution

`Authorization: Bearer cmct_…` → hash → `api_token` row → user. The
existing `CurrentUser` dependency gains a token branch, so a single
`get_current_principal` returns `(user, via, token)` where `via` is `web`
or `mcp`. Cookie auth on `/mcp` is also accepted, which makes browser-based
agents and local testing work without minting a token.

CSRF does not apply to bearer auth (no ambient credential), so the
`X-Requested-With` rule stays scoped to cookie requests.

### 4.4 Managing tokens

New admin screen **Admin › API tokens** plus a self-service section on the
profile page:

- any member creates and revokes **their own** tokens;
- an admin sees and revokes **everyone's**, and is the only one who can mint
  a non-expiring token;
- the list shows name, prefix, scopes, created, last used, expiry — never
  the token;
- creating, revoking, and expiring are audited (`entity_type=api_token`).

CLI equivalents for a headless server: `python -m app.cli token create
alice@example.com --name "Claude Code" --scopes read,write`, `token list`,
`token revoke <prefix>`.

## 5. Making agent writes visible

This is the part that makes agent access acceptable on a regulated tracker.

**`audit_event.via`** — new column, one of `web`, `mcp`, `cli`, `import`,
default `web`. Written by the service from the request principal. With it:

- the V2.0 Audit log page gains a **Source** filter and a small "via agent"
  chip on the row;
- `audit_event.changes` is unchanged, so diffs read the same;
- the period report's Change log sheet gains a Source column;
- an admin can answer "what did the agents change last week" in one filter.

**`audit_event.token_name`** — nullable string, the token's name when
`via = mcp`. Enough to tell Alice's laptop agent from the meeting-notes
automation without joining a table that may later be revoked.

Both are additive, nullable, and engine-neutral.

## 6. Tool catalogue

Naming: `cmc_<verb>_<noun>`, consistent prefix so the tools cluster in a
client's tool list. Every tool returns compact text for the model plus
`structuredContent` for programmatic use.

### 6.1 Read tools

| Tool | Input | Returns | Annotations |
|---|---|---|---|
| `cmc_whoami` | — | acting user, org, role, token name, scopes, program code, server version | readOnly, idempotent |
| `cmc_list_vocabulary` | — | active groups, categories, the six statuses, three priorities, owner orgs, and assignable people with their ids — **all valid values in one call** | readOnly, idempotent |
| `cmc_search_items` | `q`, `status[]`, `priority[]`, `group[]`, `category[]`, `owner_org[]`, `assignee`, `kind`, `due_before`, `due_after`, `sort`, `direction`, `page`, `limit` (default 25, max 100) | one compact line per item: `#42 [in_progress P1 GenSci] Title… · due 2026-10-01 · last update 2026-09-02`, plus total and page info | readOnly |
| `cmc_get_item` | `entry_no`, `include_updates` (default 5), `include_history` (default false) | every field, the newest updates, optionally the audit diffs | readOnly |
| `cmc_list_updates` | `entry_no`, `page`, `limit` | the dated timeline, newest first, with author and org | readOnly |
| `cmc_get_item_history` | `entry_no` | audit events with per-field old → new, actor, source | readOnly |
| `cmc_needs_attention` | `bucket` (`overdue`\|`due_soon`\|`stale`\|`all`), `owner_org`, `assignee` | the dashboard's needs-attention lists, agent-shaped | readOnly |
| `cmc_list_activity` | `since`, `actor`, `entity_type`, `via`, `page`, `limit` | recent changes across the program | readOnly |

### 6.2 Write tools

Split by the approval boundary in §7. **Open** tools apply immediately.
**Gated** tools create a proposal a person approves in the web UI.

| Tool | Gate | Input | Behaviour |
|---|---|---|---|
| `cmc_post_update` | **open** | `entry_no`, `body`, `occurred_on` (default today) | Appends a dated timeline entry. Append-only, attributed, destroys nothing — the same shape as creating an item, and the most common agent action. |
| `cmc_create_item` | **open** | `title`, `group`, `owner_org`, the optional rest, `kind`, `idempotency_key`, `confirm_new` | Creates an item. Runs a near-duplicate check first (§7.3) and refuses on a close title match unless `confirm_new=true`. Marked unreviewed until a person opens it. |
| `cmc_set_status` | **gated** | `entry_no`, `status`, `note`, `rationale`, `expected_updated_at` | Proposes a status change. Configurable to open per token once the team trusts it (§7.4) — the first candidate for promotion. |
| `cmc_update_item` | **gated** | `entry_no`, any patchable field, `rationale`, `expected_updated_at` | Proposes a field change. Overwrites text a person wrote, so it always needs a human. |
| `cmc_apply_batch` | **mixed** | `changes[]`, `dry_run` (default **true**) | One transaction for a set of changes. Open changes apply, gated ones become proposals, and the result says which did what. |

Every write tool takes `dry_run` and returns the exact diff it would
produce. Gated tools additionally take `rationale`, a short sentence shown
to the approver — an agent that cannot explain a change in one line
probably should not be making it.

Annotations: all write tools are `readOnlyHint: false`,
`destructiveHint: false`, `idempotentHint: false` except `cmc_set_status`,
which is idempotent. Clients that prompt on non-read-only tools therefore
prompt on all five, which is the free client-side layer described in §7.5.

### 6.3 Export tool

| Tool | Input | Returns |
|---|---|---|
| `cmc_export_workbook` | same filters as `cmc_search_items`, plus `kind` (`items`\|`period_report`), `from`, `to` | A **signed, short-lived download URL** and a summary of what it contains — never the bytes. Keeps megabytes of base64 out of the model's context and reuses the V2.0 report builders. |

### 6.4 No tools at all for

**Delete and restore**, user administration, vocabulary edits, invitations,
password resets, and Excel import.

Deleting is not gated behind approval — it is absent. There is no tool an
agent can call, with any token, any scope, or any approval, that removes an
item. Removing something from a joint regulatory tracker is a decision two
companies make deliberately in the UI, and an approval prompt is a weaker
protection than simply not building the door. The same reasoning covers
restore (it reverses a human's deliberate delete), vocabulary (renaming a
term rewrites every item carrying it), and import (it can create dozens of
rows at once).

## 7. The approval boundary

### 7.1 The line is append versus overwrite

The intuitive split is "reading and adding are safe, editing and deleting
are not." That is nearly right, and it puts one important action on the
wrong side.

**Posting a timeline update is an append, not an edit.** It adds a dated,
attributed paragraph and destroys nothing — the same shape as creating an
item. It is also the single most valuable thing an agent can do here: it is
what the spreadsheet's Status Updates cell always held, and it is the
action a person most wants automated. Gating it behind approval would cost
most of the server's usefulness to protect against a risk that does not
exist, because a wrong update is corrected by posting another one and the
original stays visible in the timeline.

So the boundary is drawn one notch differently:

| Tier | Operations | Rule |
|---|---|---|
| **Open** | every read, `cmc_create_item`, `cmc_post_update` | Applies immediately. Purely additive: nothing a person wrote is changed or lost. |
| **Gated** | `cmc_update_item`, `cmc_set_status` | Creates a proposal. A person approves or rejects it in the web UI. |
| **Absent** | delete, restore, users, vocabulary, import | No tool exists. |

`cmc_set_status` is the debatable one. It is fully reversible and fully
audited, which argues for open; but status is what both teams steer by on
the board and the dashboard, so a wrong one misleads people before anyone
notices. It starts gated and can be promoted per token (§7.4).

Clearing a field counts as overwriting, so blanking a due date or emptying
the notes column is gated like any other edit.

### 7.2 How approval works

The gated tools do not apply a change. They write a **`pending_change`**
row and return "proposed, awaiting approval" with the diff and a link.

- A person sees pending proposals in three places: a count on the
  dashboard, a badge on the item in the table and board, and a card on the
  item detail sheet showing the diff, the agent's rationale, and the token
  that proposed it.
- Approve applies the change through the normal service call, so the audit
  row records the **approver** as the actor with `via = mcp_approved` and
  the proposing token's name alongside. Accountability lands on the human
  who said yes, which is the point.
- Reject records the decision and an optional reason. Both outcomes are
  audited.
- A proposal expires after `PENDING_CHANGE_TTL_DAYS` (7) so the queue
  cannot silently accumulate.
- If the item changed after the proposal was computed, the proposal is
  marked **stale**; approving it shows the new diff and requires a second
  confirmation, so an agent's week-old edit can never quietly clobber
  yesterday's work.

**One dependency to be honest about.** V2.0 has no notifications, so a
proposal is only seen when someone opens the app. Both teams look at the
dashboard daily, and the expiry keeps stale proposals from piling up, so
this is workable — but if agent use grows, emailed proposal alerts become
the first thing worth adding from the V2.x backlog.

**A policy question for the team.** Any member can approve, since v1 §6
already lets both orgs edit everything. Whether the token's own owner may
approve their own agent's proposal is a choice: allowing it is the normal,
convenient case (you asked the agent to do it, you confirm it did it
right); forbidding it via `PENDING_CHANGE_SELF_APPROVE=false` gives true
four-eyes separation at the cost of needing a second person for every edit.
Recommendation: allow it, and revisit if an auditor asks otherwise.

### 7.3 What keeps open creates safe

Leaving creates open is the right call — it is what makes the
meeting-minutes flow work — but "additive" is not the same as "harmless"
here, for two reasons worth guarding.

**Duplicates are the real risk.** An agent that files "Stability protocol
review" when #31 already covers it creates silent drift: two rows, two
owners, two timelines for one commitment. That is arguably worse than a bad
edit, because an edit shows up in history and a duplicate shows up nowhere.
So `cmc_create_item` searches active items for a close title match first
and refuses on a strong hit, naming the candidate and asking the agent to
either post an update on the existing item or pass `confirm_new=true`.

**Entry numbers are permanent.** `entry_no` is max+1 and both teams cite it
in email and minutes. A junk item consumes a number even after it is
soft-deleted. The duplicate check and the idempotency key together make
accidental consumption unlikely, and that is the right level of effort —
protecting it further is not worth gating creates.

**Review after the fact, not approval before it.** Agent-created items
carry a "raised by agent, unreviewed" chip until a person opens or edits
them, and the dashboard lists them under needs-attention. This gives the
visibility an approval queue would give, at a fraction of the cost, without
blocking the flow that makes the feature worth having.

### 7.4 Per-token posture

Each token carries a **write mode**, so the boundary can be tightened or
relaxed per agent without code changes:

| Mode | Effect |
|---|---|
| `read_only` | no write tools at all |
| `append` | open tier only: create and post update |
| `propose` | **default** — append tier applies, gated tier proposes |
| `direct_status` | as `propose`, but status changes apply immediately |

`direct_status` is how `cmc_set_status` gets promoted for a trusted agent
once the team has seen it behave, without opening field edits. There is
deliberately no mode that applies `cmc_update_item` without a human.

`MCP_WRITES_ENABLED=false` remains the global kill switch across all modes.

### 7.5 The other guardrails

These apply across both tiers and are unchanged from the original design:

1. **`dry_run` on every write**, returning the exact diff and changing
   nothing. `cmc_apply_batch` defaults to a preview.
2. **Optimistic concurrency** via `expected_updated_at`, so a stale write
   fails with a conflict and the current item rather than overwriting a
   colleague.
3. **Idempotency keys** on create, so a retry after a timeout cannot file
   entry 58 twice.
4. **Per-token rate limits**, 60 writes and 600 reads per minute.
5. **Client-side prompts.** Because every write tool is annotated
   non-read-only, MCP clients that confirm such calls will also prompt the
   operator. This is free and worth having, but it is not the approval
   mechanism: it depends on client configuration, the operator can disable
   it, and it does not apply to headless agents. Server-side proposals are
   what actually enforce the boundary.

## 8. Errors, context, and conventions

**Errors are instructions, not status codes.** The MCP layer maps the
existing typed domain errors to messages that tell the agent what to do:

| Condition | Message |
|---|---|
| Unknown entry number | `No item #99 in GS098. The highest entry number is 57. Use cmc_search_items to find it by title.` |
| Invalid status | `"done" is not a status. Valid: open, in_progress, blocked, on_hold, completed, cancelled. Did you mean "completed"?` |
| Unknown group | `Group "Gen2 CMC" is not an active term. Active groups: General Issues, Gen1 (existing) CMC, Gen2 (Process 2.0) CMC. An admin adds terms in the web UI.` |
| Note with a status | `Notes have no status. Either set kind="action" or omit status.` |
| Stale write | `Item #42 changed at 14:02 by Wei Chen (status → blocked). Re-read it with cmc_get_item and retry.` |
| Missing scope | `This token has scope "read". Posting updates needs "write". An admin can issue a new token in Admin › API tokens.` |

**Context discipline.** Search returns one line per item, not full records.
`cmc_get_item` is the tool that returns everything, for one item at a time.
Default page size 25, hard cap 100. Long `details` and update bodies are
truncated in list output with a marker and the full text available from
`cmc_get_item`.

**Resources and prompts.** Two small additions that save the agent calls:

- Resource `cmc://program/briefing` — the program code, the vocabularies,
  the status meanings, the org conventions, and the house rule that item
  text is English with the Mandarin field optional (V2.0). An agent reads
  this once instead of discovering conventions by failing.
- Prompt `weekly_update` — takes a group and drafts the week's updates from
  recent activity, for a person to review.
- Prompt `meeting_minutes_to_changes` — turns pasted minutes into a
  `cmc_apply_batch` preview. This is the flow the CMC meeting actually
  needs, and it lands as a dry run for a person to confirm.

## 9. Data model, config, and dependencies

Migration `0003` (after V2.0's `0002`), additive and engine-neutral:

| Table | Change |
|---|---|
| `api_token` | new (unique `token_hash`; index on `user_id`); includes `write_mode` |
| `pending_change` | new — `program_id`, `item_id`, `kind` (`item_patch`\|`status_change`), `payload` JSON, `rationale`, `base_updated_at`, `proposed_by`, `token_name`, `state` (`pending`\|`applied`\|`rejected`\|`expired`), `decided_by`, `decided_at`, `decision_note`, `expires_at`; index on `(program_id, state)` |
| `audit_event` | + `via` (str(16), default `web`; `mcp`, `mcp_approved`, `cli`, `import`), + `token_name` (str(100), nullable) |
| `action_item` | + `idempotency_key` (str(64), nullable, unique per program), + `agent_reviewed_at` (datetime, nullable — null on an agent-created item until a person opens or edits it) |

New endpoints for the queue: `GET /pending-changes` (filters: state, item,
proposer), `POST /pending-changes/{id}/approve`, `POST
/pending-changes/{id}/reject`. Approval calls the same service the UI
calls, so the applied change is audited normally with the approver as
actor.

| Variable | Default | Purpose |
|---|---|---|
| `MCP_ENABLED` | `true` | mount `/mcp` |
| `MCP_TOKEN_TTL_DAYS` | `90` | default token expiry |
| `MCP_WRITES_ENABLED` | `true` | kill switch: read-only MCP without revoking tokens |
| `MCP_RATE_WRITES_PER_MIN` | `60` | per token |
| `MCP_RATE_READS_PER_MIN` | `600` | per token |
| `IDEMPOTENCY_TTL_HOURS` | `24` | create-retry window |
| `MCP_DEFAULT_WRITE_MODE` | `propose` | write mode for a new token |
| `PENDING_CHANGE_TTL_DAYS` | `7` | a proposal expires unreviewed |
| `PENDING_CHANGE_SELF_APPROVE` | `true` | may a token's owner approve their own agent's proposal (§7.2) |

One new backend dependency: `mcp` (the official Python SDK), pinned. Read
its README at implementation time rather than from memory — the ASGI
mounting helper and the `structuredContent` surface have moved between
versions. No frontend dependency beyond the two new admin/profile screens,
which use existing primitives.

**Two pieces belong in V2.0, not V2.1**, because retrofitting them costs
more than adding them now:

1. `audit_event.via` and its Audit log filter — V2.0 phase 1 is already
   building that page and that export. Adding a column and a filter chip
   there is an hour; adding it afterwards means touching the page, the
   export, and the report again.
2. The database-backed rate limiter — V2.0's quality plan already calls for
   it, and the MCP rate limits reuse it directly.

## 10. Phasing

Five tasks, a little over one v1 phase in total, on branch
`v2/mcp-agent-access`.

1. **Tokens (no MCP yet).** `api_token` model with `write_mode`, migration,
   service, scope checks, the `get_current_principal` dependency, CLI
   commands, the admin and profile screens, audit rows. Useful on its own:
   it also gives the REST API a non-cookie credential.
2. **Read-only MCP.** Mount `/mcp`, the eight read tools, the briefing
   resource, error mapping, rate limits. Ship it and let the team point an
   agent at it for a week — the cheapest way to learn whether the tool
   shapes are right before any write exists.
3. **Open writes.** `cmc_post_update` and `cmc_create_item`, the
   near-duplicate check, idempotency keys, the unreviewed chip and its
   dashboard list, `dry_run`, and the `via` and `token_name` audit fields
   flowing through. **This is the release that delivers most of the value**
   — updating entries and filing new ones, unattended, fully audited.
4. **Approval queue and gated writes.** `pending_change`, the approve and
   reject endpoints, the dashboard count, the item badge and diff card,
   expiry and staleness, then `cmc_update_item` and `cmc_set_status` on top
   of it, plus `cmc_apply_batch` spanning both tiers.
5. **Export and hardening.** `cmc_export_workbook` with signed URLs, the
   evaluation suite (§11), docs, and the tagged release.

Two sequencing calls matter here. **Read-only first** de-risks the tool
design against real agents at zero blast radius. **Open writes before the
approval queue** means the team gets the valuable half early and can decide
from experience whether the queue in step 4 is worth building, or whether
field edits should simply stay in the web UI. If they choose the latter,
step 4 shrinks to nothing and the design still holds.

## 11. Testing and evaluation

Beyond the project's existing layers:

- **Tool unit tests** call each tool function directly against the test
  database, asserting the service was invoked, the audit row carries
  `via="mcp"` and the token name, and the text output stays compact.
- **Scope and auth tests**: a `read` token is refused on every write tool; a
  deactivated user's token is refused everywhere; a revoked token is refused
  immediately; an expired token names its expiry.
- **Guardrail tests**: `dry_run` mutates nothing (asserted by comparing the
  full table state before and after); a stale `expected_updated_at` raises
  conflict; a repeated idempotency key returns the original item and creates
  no second row; a batch with one bad change commits nothing.
- **Protocol smoke** with the MCP Inspector against a running container,
  plus a CI job that lists tools over streamable HTTP and calls `cmc_whoami`
  with a seeded token.
- **An evaluation suite** of ten questions in the skill's XML format, run
  against the demo-seeded database from the quality plan, checking that an
  agent can actually accomplish realistic tasks: find the overdue P1 items
  for one org, post an update on the right entry, reconcile a status against
  the history, and refuse to act when a value is not in the vocabulary.
  These are read-only and stable, so they can run in CI.

## 12. Risks

| Risk | Mitigation |
|---|---|
| An agent overwrites something a person wrote | It cannot: field and status changes are proposals a person approves, and the audit row names the approver |
| An agent files a duplicate or junk item | Near-duplicate check refuses close title matches; idempotency keys stop retry doubles; agent-created items are chipped unreviewed and listed on the dashboard |
| A proposal sits unseen because there are no notifications | Dashboard count, item badge, and a 7-day expiry; emailed alerts are the first V2.x item to pull in if agent use grows |
| Approval becomes a rubber stamp | The diff and the agent's rationale are shown, not just a yes button; stale proposals force a second confirmation against the current item |
| A token leaks | Hashed at rest, prefix-identifiable, revocable instantly, expiring by default, scoped to one user's own permissions, and `MCP_WRITES_ENABLED=false` disables all writes at once |
| Agents flood the database | Per-token rate limits, hard page caps, and the same single-container profile the UI already runs in |
| Tool surface churn breaks clients | Tool names and required arguments are treated as an API: additive changes only within a major version, and `cmc_whoami` reports the server version |
| MCP SDK churn | Pinned version, a protocol smoke test in CI, and the adapter confined to `app/mcp/` so a SDK change never reaches a service |
| Two agents edit the same item | `expected_updated_at` turns a silent overwrite into a conflict the agent must resolve |

## 13. Acceptance

- An admin mints a `read,write` token in `propose` mode for a member; the
  raw token is shown once and never again, and the listing shows only its
  prefix.
- An agent with that token calls `cmc_whoami` and gets the member's name,
  org, scopes, and write mode.
- **Open path:** the agent finds entry 42 by searching its title, reads it,
  and posts a dated update — no browser, no prompt, applied immediately.
  The web UI shows the update in the timeline and the History tab marks it
  "via agent" with the token's name.
- **Open path, create:** the agent files a new action item; it appears with
  an "unreviewed" chip and on the dashboard's needs-attention list until a
  person opens it. Filing a near-identical title instead returns the
  existing entry number and refuses without `confirm_new`.
- **Gated path:** the agent proposes a due-date change. Nothing changes on
  the item. A count appears on the dashboard, a badge on the item, and the
  detail sheet shows the diff plus the agent's rationale. Approving applies
  it and audits the **approver** as the actor; rejecting records the
  decision. Both are visible in the Audit log filtered by source.
- A proposal whose item changed in the meantime is flagged stale and
  requires a second confirmation showing the new diff.
- A token in `append` mode is refused on the gated tools with a message
  naming its mode; a `read` token is refused on every write.
- No tool exists for delete, restore, users, vocabulary, or import — the
  agent's tool list simply does not contain them.
- `cmc_apply_batch` with six changes returns a preview by default; run for
  real it applies the open ones and queues the gated ones, and says which
  did what.
- Revoking the token stops the next call immediately; `MCP_WRITES_ENABLED=false`
  stops all writes while leaving reads working.
- `docker compose up -d` from a V2.0 volume serves `/mcp` with no new
  container, no new port, and no new required environment variable.
