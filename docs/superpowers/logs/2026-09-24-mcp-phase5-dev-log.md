# MCP Phase 5 — Export, evaluation, hardening, docs: dev log

Date: 2026-09-24
Design: `docs/superpowers/specs/2026-09-19-mcp-agent-access-design.md` §6.3, §10 item 5, §11, §13
Branch: `claude/optimistic-davinci-wpxhpl` (PR #6)

This is the last phase of the MCP design. It ends with the line-by-line check
of §6.3, §11 and §13 that Phase 2's addendum promised every phase would get.
There was no separate plan document: the scope was §10 item 5 plus the gaps
this check turned up.

## What was built

| Piece | Where |
|---|---|
| `cmc_export_workbook`: search filters in, a summary and a 15-minute link out, never bytes | `app/mcp/tools_export.py` |
| Signed links: stateless HMAC bound to a purpose, with expiry (410 when expired) | `app/services/signed_links.py` |
| Export links name the user and API token; both must still be live when fetched | `app/services/export_links.py` |
| `GET /api/export/link/{token}`: the link is the credential, no session | `app/api/exports.py` |
| A refused token says why: unknown, revoked (date), expired (date), deactivated owner | `app/services/tokens.py` `why_refused` |
| Fictional 12-item evaluation programme, and `python -m app.cli seed-eval` | `app/evaluation/seed.py`, `app/cli.py` |
| Ten evaluation questions in the mcp-builder XML format | `docs/mcp/evaluation.xml` |
| A test that derives all ten answers through the tools and compares them with the XML | `tests/eval/test_evaluation.py` |
| No-mutation, compactness, and scope guarantees across every tool | `tests/mcp/test_guarantees.py` |
| CI: `mcp-smoke` job (real HTTP + the MCP Inspector); the container smoke calls `/mcp` | `.github/workflows/ci.yml`, `scripts/` |
| Docs: README tool table and export notes, DEPLOYMENT MCP section, design §14 register | `README.md`, `docs/` |

## Issues found, and what was done

1. **The SDK sent every result twice.** Running the official MCP Inspector
   against the server showed each `str` result repeated verbatim as
   `structuredContent`. That doubles every response an agent reads, working
   against §8's compactness. Every tool now sets `structured_output=False`;
   `test_results_carry_the_text_once` holds it.
2. **§13 said a stale confirm "returns the new diff"; it did not.** It named who
   changed what and told the agent to start over. The confirm call already
   plans the change against the item as it is now, so it now returns that diff
   with a fresh token. `test_a_stale_confirm_returns_the_new_diff_and_a_fresh_token`
   walks the whole path to an applied change.
3. **§11 asks that a read token be refused on *every* write tool;** two were
   tested. `test_a_read_token_is_refused_on_every_write_tool` finds the write
   tools from their annotations, so a new one cannot ship without a case.
4. **`token create` on the CLI ignored `MCP_TOKEN_TTL_DAYS`.** It hard-coded 90
   days while the web API honoured the setting. Fixed, with a test.
5. **An expired token was refused without saying so** (§11: "an expired token
   names its expiry"). `why_refused` now names the reason and the date.
6. **History printed internal update ids** (`update_id: None → 3`) under every
   posted update. Hidden; the summary line already says what happened.
7. **SDK argument aliases are broken.** `Field(alias="from")` is advertised in
   the schema but the call passes `from` to the function and crashes. So the
   export takes `from_date`/`to_date` (see deviations).

## Deviations from the design

All are in the design's new §14 register with the others from Phases 1–4.

| Design | Built | Why |
|---|---|---|
| §6.3 `from`, `to` | `from_date`, `to_date`; the item-kind filter is `item_kind` | `from` is a Python keyword and aliases break (issue 7); `kind` already means the export kind |
| §6.3 `period_report` from the V2.0 report builders | **Refused**, saying the builder does not exist yet | V2.0 has not been built. This is a dependency, not a choice |
| §11 Inspector "against a running container" | The container smoke calls `tools/list` and `cmc_whoami` with curl; the Inspector runs in the `mcp-smoke` job against the app | The image has no Node, and should not |
| §11 evaluation "run in CI" | CI proves every answer is reachable through the tools; **asking a model the questions needs an API key**, so it is a manual step | CI has no model credentials |

## Line-by-line check

### §6.3 Export tool

| Requirement | Status |
|---|---|
| Same filters as `cmc_search_items` | Yes, through the shared `build_filters`; `kind` renamed `item_kind` |
| `kind` `items` \| `period_report` | `items` yes; `period_report` refused (V2.0 dependency) |
| `from`, `to` | As `from_date`/`to_date`; accepted only for `period_report`, refused otherwise with a pointer to `due_after`/`due_before` |
| Signed, short-lived URL, never the bytes | Yes: HMAC, 15 minutes, revoked token or inactive owner kills it; summary under 2 kB (tested) |
| A summary of what it contains | Row count, filters in words, column names, expiry |

### §11 Testing and evaluation

| Requirement | Status |
|---|---|
| Tool tests assert `via="mcp"`, token name, compact output | Yes (Phase 3/4 tests, `test_search_output_stays_compact`) |
| Read token refused on every write tool | Yes, now across all five (issue 3) |
| Deactivated user's token refused everywhere; revoked immediately | Yes (`test_runtime.py`) |
| Expired token names its expiry | Yes, now (issue 5) |
| Preview mutates nothing, by full table comparison | Yes (`test_no_preview_or_dry_run_changes_any_table`) |
| Confirm token refused for a changed item, tampered, or expired | Yes (`test_confirm.py`, `test_edit_tools.py`) |
| Idempotency key returns the original, no second row | Yes (`test_write_tools.py`) |
| A batch with one bad change commits nothing | Yes (`test_edit_tools.py`) |
| Undo restores exactly what it changed, records `reverted`, works on a human's change, refuses twice | Yes (`test_revert.py`, `test_revert_api.py`) |
| Protocol smoke with the Inspector; CI lists tools and calls `cmc_whoami` | Yes, with the split noted above |
| Ten-question evaluation over the demo data | Written and proven reachable; the model run is manual |

### §13 Acceptance

| Criterion | Status |
|---|---|
| Admin mints a `read,write` interactive token for a member; raw once, prefix after | Yes (Phase 1) |
| `cmc_whoami` gives name, org, scopes, write mode | Yes |
| Open path: find, read, post an update; timeline shows it; History marks it agent with the token name | Yes |
| Create: unreviewed chip and dashboard notice; near-duplicate refused without `confirm_new` | Yes; clears on *Looks right* or an edit rather than on opening (Phase 3 deviation) |
| Confirm path in one conversation | Yes |
| Item edited between the calls: refused, new diff returned | Yes, now (issue 2) |
| Undo path: bar with diff and token name, dashboard count, one-click undo or acknowledge | Yes (Phase 4) |
| No identity parameters; attempting one names the web app | Yes (`StrictArguments`) |
| Append token refused on edits naming its mode; read token refused on every write | Yes |
| No delete, restore, users, vocabulary, or import tools | Yes (smoke checks the tool list) |
| A six-change batch: one preview, one token, all or none | Yes |
| Revoking stops the next call; `MCP_WRITES_ENABLED=false` stops writes, reads work | Yes |
| `docker compose up -d` serves `/mcp` with nothing new to configure | Yes by defaults; the container smoke now proves it in CI (Docker is not available in this dev environment) |

## Not done, and why

- **The release tag.** Pushing `v*` publishes an image to GHCR, which is an
  outward-facing act for a maintainer to take.
- **Running a model on `docs/mcp/evaluation.xml`.** Needs an API key.
- **`period_report` and the Audit log page.** Both wait on V2.0.
- **The container smoke was not run locally** (no Docker here); CI runs it.

## Numbers

| | End of Phase 4 | End of Phase 5 |
|---|---|---|
| Backend tests | 309 | 337 |
| Backend coverage | not recorded | 93.5% (gate 80%) |
| Frontend tests | 49 | 49 (untouched) |
| MCP tools | 13 | 14 |

Green: `ruff check`, `ruff format --check`, the backend suite with the coverage
gate, `alembic check`, frontend lint, typecheck, tests and build,
`scripts/mcp-smoke.sh` with the Inspector.
