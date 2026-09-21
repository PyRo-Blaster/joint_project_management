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
| Write boundary | **Append applies, edits confirm in-conversation, delete does not exist** (§7) | Additive work runs unattended. An edit is previewed and confirmed in the same conversation, then stays undoable for 14 days. No approval queue, no second inbox. |
| Editable surface | An agent may change an item's **live state**, never its **identity** (§7.2) | Title, group, owner org and kind are not tool parameters at all, so they need no guarding. |
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
| `write` | the write tools, subject to the token's write mode (§7.6) — `append` is additive only, `interactive` adds edits behind the confirm handshake |

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

Split by the boundary in §7. **Open** tools apply immediately. **Confirm**
tools return a diff and a token on the first call and apply on the second,
so the person approves in the conversation they are already having.

| Tool | Gate | Input | Behaviour |
|---|---|---|---|
| `cmc_post_update` | **open** | `entry_no`, `body`, `occurred_on` (default today) | Appends a dated timeline entry. Append-only, attributed, destroys nothing — the same shape as creating an item, and the most common agent action. |
| `cmc_create_item` | **open** | `title`, `group`, `owner_org`, the optional rest, `kind`, `idempotency_key`, `confirm_new` | Creates an item. Runs a near-duplicate check first (§7.3) and refuses on a close title match unless `confirm_new=true`. Marked unreviewed until a person opens it. |
| `cmc_set_status` | **confirm** | `entry_no`, `status`, `note`, `confirm` | Returns the diff and a confirm token; the second call applies it. |
| `cmc_update_item` | **confirm** | `entry_no`, any of `due_on`, `priority`, `category`, `assignee`, `details`, `notes_risks`, `file_path`, `confirm` | Same handshake. Title, group, owner org and kind are **not parameters** (§7.2). |
| `cmc_apply_batch` | **confirm** | `changes[]`, `confirm` | One transaction for a set of changes: the first call previews all of them and returns a single token covering the set, the second applies them all or none. |

The open tools take `dry_run` and return the diff they would produce. The
confirm tools *are* a dry run on their first call, so the two ideas
collapse: call without `confirm` to see the diff, call with it to apply.

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

## 7. The approval mechanism

### 7.1 Why the queue was the wrong shape

The first draft of this design gated edits behind a `pending_change`
queue: the agent proposes, a person finds the proposal in the app and
approves it. It is the obvious answer and it is more machinery than the
problem deserves.

A queue is **a second inbox**. Inboxes need notifications to be seen, they
accumulate stale entries, they need an expiry job, and they need their own
review screen. Worse, the human loop is asynchronous: the agent finishes
its turn not knowing whether the change landed, and the person has to
context-switch into the app later to finish a job they already asked for.
That is the tedium, and it is in the shape, not the details.

Three moves remove almost all of it.

### 7.2 Move one — shrink what an agent can edit

Most of the machinery existed to guard fields that an agent has no business
touching in the first place. Not exposing them is simpler than guarding
them, and it is the same reasoning that removed the delete tool.

| Agent-editable | Never agent-editable |
|---|---|
| `status`, `due_on`, `priority`, `category`, `assignee`, `details`, `notes_risks`, `file_path` | `title`, `group`, `owner_org`, `kind`, `entry_no` |

The right column is the item's identity and its accountability. `title` is
how both teams refer to the item in email and minutes; `owner_org` and
`group` assign work between two companies; `kind` and `entry_no` are
structural. Those change in the web UI, by a person, deliberately.

The left column is the item's live state — the things that legitimately
move week to week, and precisely what an agent is useful for. Every one of
them is a single value that is obvious when wrong and trivial to correct.

### 7.3 Move two — confirm in the conversation, not in a queue

The person who should approve an agent's edit is almost always **already in
the conversation with it**. Sending them to a queue in another application
to approve a change they just asked for is the tedium. So the confirmation
happens where they are, in a two-call handshake:

1. The agent calls `cmc_update_item(entry_no=42, due_on="2026-11-15")`.
   The server changes nothing and returns the exact diff plus a
   **confirm token**:
   `due_on: 2026-10-01 → 2026-11-15. Confirm with confirm="ct_…" (valid 10 minutes).`
2. The agent shows the diff and asks. The person says yes.
3. The agent calls again with `confirm`, and the change applies.

**The token is stateless** — an HMAC over the item id, the canonical patch,
the item's `updated_at` at step 1, and an expiry, signed with the existing
`SECRET_KEY`. Nothing is stored, so there is no table, no state machine,
no expiry job to sweep.

It also gives three things free:

- **Staleness detection.** The base `updated_at` is signed into the token,
  so if someone edited the item between the two calls, the confirm fails
  with the new diff. The optimistic-concurrency guardrail disappears into
  this step rather than being its own mechanism.
- **Tamper resistance.** The patch is signed, so the agent cannot confirm a
  change different from the one it previewed.
- **A free second prompt.** Because both calls are annotated non-read-only,
  clients that confirm such calls prompt the operator anyway.

### 7.4 Move three — Undo instead of approval for catching mistakes

Steps 7.2 and 7.3 handle "is this the right change". What remains is "the
agent and I both got it wrong", and for that **reversal beats prevention**.

Every agent change is flagged on the item and reversible in one click for
`AGENT_UNDO_DAYS` (14):

- The item detail sheet shows a slim bar: *"Agent changed due date
  2026-10-01 → 2026-11-15, 2 hours ago, via Alice's Claude Code.
  [Undo] [Looks right]"*
- The dashboard shows *"4 agent changes awaiting your eye"* linking to the
  filtered list.
- Acknowledging is one click, and happens implicitly when a person edits
  the item themselves.

**Undo needs no new storage either.** The audit event already stores
`{field: {old, new}}`, so reversing is building the inverse patch and
applying it through the normal service call. It lands as an ordinary
audited event with action `reverted`, roughly thirty lines of service code
— and it is independently useful for human mistakes, which the app cannot
do today at all.

For a regulated change history this is arguably *better* than a queue. An
approved-or-rejected proposal leaves the rejected version nowhere; a change
and its reversal both sit in the trail, which is exactly what a change
history is supposed to show.

### 7.5 What about agents with nobody watching?

A scheduled or headless agent has no one to confirm with, which is the one
case a queue genuinely solved. The simpler answer is that the correct
response to "nobody is watching" is **no**, not "ask someone later".

Headless agents get a token in `append` mode: they can post updates and
create items — the additive work that needs no supervision — and they
cannot edit at all. If the team later wants unattended edits, that is the
moment to revisit a queue, with real usage to justify it.

### 7.6 The resulting mechanism

| Operation | Mechanism |
|---|---|
| Every read | Direct |
| `cmc_post_update`, `cmc_create_item` | Direct, plus the create guardrails in §7.7 |
| `cmc_set_status`, `cmc_update_item` (editable fields only) | Preview → confirm token → apply, then flagged and undoable for 14 days |
| Title, group, owner org, kind | No tool parameter exists |
| Delete, restore, users, vocabulary, import | No tool exists |
| Anything at all, headless | `append` mode: additive only |

Per-token write modes reduce to three: `read_only`, `append`, and
`interactive` (the default — append applies, edits need the confirm
handshake). `MCP_WRITES_ENABLED=false` is still the global kill switch.

What this removed, relative to the queue design: one table with a state
machine, three endpoints, a review screen with diff cards, an expiry job,
the staleness logic, the self-approval policy question, and three config
variables. What it added: one undo endpoint, one banner, one dashboard
tile, and an HMAC helper. It is roughly a third of the work, and the person
never leaves the conversation to finish a change they asked for.

### 7.7 What keeps open creates safe

Unchanged from the previous draft, because it was already cheap and it
guards the one real risk of unattended creates.

**Duplicates are the risk, not junk.** An agent that files "Stability
protocol review" when #31 already covers it creates silent drift: two rows,
two owners, two timelines for one commitment. An edit shows up in history;
a duplicate shows up nowhere. So `cmc_create_item` searches active items
for a close title match and refuses a strong hit, naming the candidate and
asking the agent to either post an update on it or pass `confirm_new=true`.

**Entry numbers are permanent.** `entry_no` is max+1 and both teams cite it
in email and minutes; a junk item consumes a number even after a soft
delete. The duplicate check plus the idempotency key make that unlikely
enough, and that is the right level of effort.

**Review after, not approval before.** Agent-created items carry an
"unreviewed" chip and sit on the dashboard list until a person opens them —
the same surface as the undo bar in §7.4, so there is one place to look,
not two.

### 7.8 The remaining guardrails

1. **`dry_run` on every write**, returning the exact diff and changing
   nothing. For edits this is what the first handshake call already does,
   so the two collapse into one idea.
2. **Idempotency keys** on create, so a retry after a timeout cannot file
   entry 58 twice.
3. **Per-token rate limits**, 60 writes and 600 reads per minute.
4. **Client-side prompts**, free from the non-read-only annotations.
5. **Everything attributed**: `via` and `token_name` on every audit row, so
   the Audit log answers "what did the agents change" in one filter.

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
| `audit_event` | + `via` (str(16), default `web`; `mcp`, `cli`, `import`), + `token_name` (str(100), nullable), + `reverted_by_event_id` (int, nullable) |
| `action_item` | + `idempotency_key` (str(64), nullable, unique per program), + `agent_ack_at` / `agent_ack_by` (nullable — set when a person acknowledges or edits after an agent touched the item) |

No table for proposals: the confirm token is a stateless HMAC and undo
reads the audit row it reverses.

One new endpoint, `POST /activity/{event_id}/revert`, which builds the
inverse patch from the event's `changes` and applies it through the normal
service call, recording a `reverted` event that points back. Plus `POST
/items/{id}/ack` for the one-click "looks right". Both are ordinary member
capabilities, not admin.

| Variable | Default | Purpose |
|---|---|---|
| `MCP_ENABLED` | `true` | mount `/mcp` |
| `MCP_TOKEN_TTL_DAYS` | `90` | default token expiry |
| `MCP_WRITES_ENABLED` | `true` | kill switch: read-only MCP without revoking tokens |
| `MCP_RATE_WRITES_PER_MIN` | `60` | per token |
| `MCP_RATE_READS_PER_MIN` | `600` | per token |
| `IDEMPOTENCY_TTL_HOURS` | `24` | create-retry window |
| `MCP_DEFAULT_WRITE_MODE` | `interactive` | write mode for a new token |
| `MCP_CONFIRM_TTL_MINUTES` | `10` | confirm-token validity |
| `AGENT_UNDO_DAYS` | `14` | how long an agent change stays one-click reversible |

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
4. **Edits with confirm and undo.** The HMAC confirm helper, `cmc_set_status`
   and `cmc_update_item` over the narrowed field set, `cmc_apply_batch`, the
   revert service and endpoint, the agent-change bar on the item, and the
   dashboard tile. The undo half is independently useful: it is the first
   time anyone, agent or human, can reverse a change from the UI.
5. **Export and hardening.** `cmc_export_workbook` with signed URLs, the
   evaluation suite (§11), docs, and the tagged release.

Two sequencing calls matter. **Read-only first** de-risks the tool design
against real agents at zero blast radius. **Open writes before edits** means
the team gets the valuable half early, and step 4 remains optional: if
posting updates and filing items turns out to be enough, field edits can
simply stay in the web UI and nothing else in the design changes.

## 11. Testing and evaluation

Beyond the project's existing layers:

- **Tool unit tests** call each tool function directly against the test
  database, asserting the service was invoked, the audit row carries
  `via="mcp"` and the token name, and the text output stays compact.
- **Scope and auth tests**: a `read` token is refused on every write tool; a
  deactivated user's token is refused everywhere; a revoked token is refused
  immediately; an expired token names its expiry.
- **Guardrail tests**: a first-call preview mutates nothing (asserted by
  comparing full table state before and after); a confirm token for a
  changed item is refused; a tampered or expired token is refused; a
  repeated idempotency key returns the original item and creates no second
  row; a batch with one bad change commits nothing.
- **Undo tests**: reverting an event restores every field it changed and
  only those, records a `reverted` event pointing at the original, works on
  a human's change as well as an agent's, and refuses twice on the same
  event.
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
| An agent overwrites something a person wrote | It cannot touch the item's identity at all (§7.2); a live-state edit is previewed, confirmed in the conversation, flagged on the item, and one click to reverse for 14 days |
| A confirm token is replayed or tampered with | It is an HMAC over the item, the exact patch and the base version, valid ten minutes and single-use in effect: a changed item invalidates it |
| An agent files a duplicate or junk item | Near-duplicate check refuses close title matches; idempotency keys stop retry doubles; agent-created items are chipped unreviewed and listed on the dashboard |
| The person confirms without really reading the diff | Unavoidable in any design; undo is the backstop, and the change plus its reversal both stay in the audit trail, which a rejected proposal would not |
| An agent change is never noticed | The item bar and the dashboard tile persist until someone acknowledges; unlike a queue there is no expiry that quietly drops it |
| A headless agent makes an unsupervised edit | It cannot: `append` mode has no edit tools at all |
| A token leaks | Hashed at rest, prefix-identifiable, revocable instantly, expiring by default, scoped to one user's own permissions, and `MCP_WRITES_ENABLED=false` disables all writes at once |
| Agents flood the database | Per-token rate limits, hard page caps, and the same single-container profile the UI already runs in |
| Tool surface churn breaks clients | Tool names and required arguments are treated as an API: additive changes only within a major version, and `cmc_whoami` reports the server version |
| MCP SDK churn | Pinned version, a protocol smoke test in CI, and the adapter confined to `app/mcp/` so a SDK change never reaches a service |
| Two agents edit the same item | `expected_updated_at` turns a silent overwrite into a conflict the agent must resolve |

## 13. Acceptance

- An admin mints a `read,write` token in `interactive` mode for a member; the
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
- **Confirm path:** the agent calls to move a due date. Nothing changes;
  it gets the diff and a token. It shows the diff, the person says yes, the
  second call applies it — all inside one conversation, with no visit to
  another screen.
- If someone edits the item between the two calls, the confirm fails and
  returns the new diff rather than applying a stale change.
- **Undo path:** the item shows an agent-change bar with the diff and the
  token name; the dashboard counts it. One click reverses it, recording a
  `reverted` event that points at the original. One click acknowledges it
  instead, and the bar clears.
- `cmc_update_item` has no parameter for title, group, owner org, or kind;
  attempting one is a schema error naming the web UI as the place to do it.
- A token in `append` mode is refused on the edit tools with a message
  naming its mode; a `read` token is refused on every write.
- No tool exists for delete, restore, users, vocabulary, or import — the
  agent's tool list simply does not contain them.
- `cmc_apply_batch` with six changes returns one preview and one token;
  confirming applies all six or none.
- Revoking the token stops the next call immediately; `MCP_WRITES_ENABLED=false`
  stops all writes while leaving reads working.
- `docker compose up -d` from a V2.0 volume serves `/mcp` with no new
  container, no new port, and no new required environment variable.
