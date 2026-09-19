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
| Destructive tools | **Not exposed in V2.1** — no delete, no restore, no user admin, no import | The blast radius of an agent mistake on a regulated tracker is the thing to control first. Those stay in the web UI. |
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
| `write` | create item, update item, set status, post update, apply batch |

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

| Tool | Input | Behaviour | Annotations |
|---|---|---|---|
| `cmc_post_update` | `entry_no`, `body`, `occurred_on` (default today), `dry_run` | Appends a timeline entry. **The most common agent action** — a dated note of what happened, exactly what the spreadsheet's Status Updates cell used to hold. | not readOnly, not idempotent, not destructive |
| `cmc_set_status` | `entry_no`, `status`, `note` (optional, posted as an update in the same transaction), `expected_updated_at`, `dry_run` | The second most common action, given its own tool so the agent does not have to reach for a generic patch. Setting `completed` fills `completed_on`. | not readOnly, not destructive |
| `cmc_update_item` | `entry_no`, any of the patchable fields, `expected_updated_at`, `dry_run` | Partial update, the same `ItemPatch` shape the UI uses. | not readOnly, not destructive |
| `cmc_create_item` | `title`, `group`, `owner_org`, and the optional rest; `kind` (`action`\|`note`), `idempotency_key`, `dry_run` | Creates an item; `entry_no` is assigned as max+1, same as the UI. | not readOnly, not idempotent |
| `cmc_apply_batch` | `changes[]` (each an update, status change, or post), `dry_run` (default **true**) | One transaction for a set of changes — the "I read the meeting minutes, apply these six things" case. All-or-nothing. Defaults to a preview. | not readOnly, not destructive |

### 6.3 Export tool

| Tool | Input | Returns |
|---|---|---|
| `cmc_export_workbook` | same filters as `cmc_search_items`, plus `kind` (`items`\|`period_report`), `from`, `to` | A **signed, short-lived download URL** and a summary of what it contains — never the bytes. Keeps megabytes of base64 out of the model's context and reuses the V2.0 report builders. |

### 6.4 No tools for

Delete, restore, user administration, vocabulary edits, invitations,
password resets, and Excel import. Each is either destructive, privileged,
or rare enough that the web UI is the right place. An agent that needs one
says so; a person does it.

## 7. Guardrails

Five mechanisms, each cheap and each closing a specific failure mode.

1. **`dry_run` on every write.** Returns the exact diff that would be
   applied — old → new per field — and changes nothing. `cmc_apply_batch`
   defaults to `dry_run=true`, so the agent must consciously commit a
   multi-item change. This is the single most valuable guardrail: it lets
   the agent check its own work, and lets a person approve a preview.

2. **Optimistic concurrency.** `expected_updated_at` on updates. If the
   item changed since the agent read it, the call fails with `conflict` and
   returns the current item so the agent can re-read and retry rather than
   silently overwriting a colleague. This is the V2.x optimistic-locking
   idea, pulled forward because agents make the race far more likely than
   two people ever did.

3. **Idempotency keys** on `cmc_create_item`. A retry after a timeout must
   not create entry 58 twice. The key is stored with the item for
   `IDEMPOTENCY_TTL_HOURS` (24) and a repeat returns the original.

4. **Rate limits per token.** 60 writes per minute, 600 reads per minute,
   enforced by the same sliding-window limiter the login path uses (moved
   to a database-backed limiter so it survives multiple workers). A limited
   call returns `rate_limited` with the retry delay.

5. **Validation before the model sees a failure.** Every enum error names
   the valid values in the message, and every unknown group or category
   suggests the closest active term. The agent fixes its own call instead of
   guessing twice.

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
| `api_token` | new (unique `token_hash`; index on `user_id`) |
| `audit_event` | + `via` (str(8), default `web`), + `token_name` (str(100), nullable) |
| `action_item` | + `idempotency_key` (str(64), nullable, unique per program) |

| Variable | Default | Purpose |
|---|---|---|
| `MCP_ENABLED` | `true` | mount `/mcp` |
| `MCP_TOKEN_TTL_DAYS` | `90` | default token expiry |
| `MCP_WRITES_ENABLED` | `true` | kill switch: read-only MCP without revoking tokens |
| `MCP_RATE_WRITES_PER_MIN` | `60` | per token |
| `MCP_RATE_READS_PER_MIN` | `600` | per token |
| `IDEMPOTENCY_TTL_HOURS` | `24` | create-retry window |

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

Four tasks, roughly one v1 phase in total, on branch `v2/mcp-agent-access`.

1. **Tokens (no MCP yet).** `api_token` model, migration, service, scope
   checks, the `get_current_principal` dependency, CLI commands, the admin
   and profile screens, audit rows. Testable and useful on its own: it also
   gives the REST API a non-cookie credential.
2. **Read-only MCP.** Mount `/mcp`, the eight read tools, the briefing
   resource, error mapping, rate limits. Ship it and let the team point an
   agent at it in read-only mode for a week — the cheapest way to find out
   whether the tool shapes are right before any write exists.
3. **Writes.** The five write tools, `dry_run`, `expected_updated_at`,
   idempotency keys, the `via` and `token_name` audit fields flowing
   through, the two prompts.
4. **Export and hardening.** `cmc_export_workbook` with signed URLs, the
   evaluation suite (§11), docs, and the tagged release.

Shipping read-only first is the important call here. It de-risks the tool
design with real agents at zero blast radius.

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
| An agent writes plausible but wrong content to a regulated tracker | Nothing is destructive; every change is reversible by editing; the audit trail names the token; `dry_run` and the batch default let a person approve first; read-only phase first |
| A token leaks | Hashed at rest, prefix-identifiable, revocable instantly, expiring by default, scoped to one user's own permissions, and `MCP_WRITES_ENABLED=false` disables all writes at once |
| Agents flood the database | Per-token rate limits, hard page caps, and the same single-container profile the UI already runs in |
| Tool surface churn breaks clients | Tool names and required arguments are treated as an API: additive changes only within a major version, and `cmc_whoami` reports the server version |
| MCP SDK churn | Pinned version, a protocol smoke test in CI, and the adapter confined to `app/mcp/` so a SDK change never reaches a service |
| Two agents edit the same item | `expected_updated_at` turns a silent overwrite into a conflict the agent must resolve |

## 13. Acceptance

- An admin mints a `read,write` token for a member; the raw token is shown
  once and never again, and the listing shows only its prefix.
- An agent configured with that token calls `cmc_whoami` and gets the
  member's name, org, and scopes.
- The agent finds entry 42 by searching its title, reads it, posts a dated
  update, and sets the status to blocked with a note — three calls, no
  browser.
- The web UI shows that update in the timeline, the History tab shows the
  two changes with a "via agent" source and the token's name, and the Audit
  log filters to them by source.
- A `read`-scoped token attempting the same write is refused with a message
  naming the missing scope.
- `cmc_apply_batch` with six changes returns a preview by default; run with
  `dry_run=false` it applies all six or none.
- Revoking the token stops the next call immediately.
- `docker compose up -d` from a V2.0 volume serves `/mcp` with no new
  container, no new port, and no new required environment variable.
