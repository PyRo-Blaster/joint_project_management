# MCP Phase 2 Development Log

Branch: `claude/optimistic-davinci-wpxhpl`. Started 2026-09-21.
Plan: `docs/superpowers/plans/2026-09-21-mcp-phase2-read-only-server.md`.
Design: `docs/superpowers/specs/2026-09-19-mcp-agent-access-design.md`.

Phase 2 delivers the MCP endpoint itself: eight read-only tools and a
programme briefing resource, served at `/mcp` from the existing container.

## Environment

- uv 0.8.17; backend on **Python 3.13.12** (`uv run --python 3.13 pytest`), the
  same constraint the last three logs record.
- Baseline before starting: 164 backend tests, 39 frontend tests.

## The SDK is not what the design assumed

The design named FastMCP. **That API no longer exists.** `mcp` resolves to
**2.2.0**, which renamed it and changed several things that only surfaced by
running the library. Everything below was confirmed with a throwaway prototype
*before* any plan was written, which is why this phase had no false starts.

| Finding | Consequence |
|---|---|
| `mcp.server.fastmcp` raises `ModuleNotFoundError` with a migration hint; the class is now `mcp.server.mcpserver.MCPServer` | Every import in the design is stale |
| Mounting the sub-app alone raises `RuntimeError: Task group is not initialized` at the first request | The sub-app's `router.lifespan_context` must run inside the parent app's lifespan. `create_app()` grew a lifespan solely for this. |
| Unconfigured, the transport answers `421 Invalid Host header` | DNS-rebinding protection is on by default and needs an explicit host list, or disabling |
| `ctx.headers` carries the HTTP request headers, `None` on stdio | How a tool sees the bearer token |
| `ToolError` returns `is_error=True` with the message for the model; anything else is a crash | All domain errors are mapped to it in one place |
| Sync tool functions are **not** offloaded to a thread | Tools are `async` and hand blocking database work to `anyio.to_thread.run_sync` |

Reading the library beats trusting a design document written from memory. The
design's §3 wording should be corrected to `MCPServer` when it is next touched.

## Decisions taken while planning

1. **`/mcp` accepts bearer tokens only, never the session cookie.** The design
   (§4.3) allowed cookies too. Refusing them is strictly safer and it is what
   lets DNS-rebinding protection default to off: with no ambient credential,
   a rebinding attack has nothing to steal. `MCP_ALLOWED_HOSTS` turns host
   checking on for anyone who wants belt and braces.
2. **Tools are `async` with the body on a worker thread**, via one `call_tool`
   helper so no tool repeats the plumbing.
3. **`entry_no` is the handle.** Tools take the number both teams say out loud;
   `cmc_get_item` returns the internal id alongside it.
4. **The briefing resource is unauthenticated** and exposes programme
   conventions and vocabularies only, never item data. A resource has no
   `Context`, so it could not read a token even if it wanted one.

## Implementation notes

**Tools call services, never routers.** `app/mcp/` is a sibling of `app/api/`,
exactly as the flow map draws it. Every tool body is a plain function taking
`(db, caller, program)`, which makes each one directly unit-testable without
the protocol.

**One test-harness surprise.** MCP tools open their own session from the
process-wide factory rather than through FastAPI's injector, because they are
not FastAPI endpoints. The suite's `app` fixture only overrides the injector, so
the first tool call hit `no such table: api_token`. The fix was in the test
fixtures, not the product: `mcp_client` now depends on `cli_db`, which points
the global factory at the test engine. Production was always correct, since the
app configures that factory at startup.

**Error copy does the work the spec asked for.** A missing item names the
highest entry number and points at `cmc_search_items`; a missing token says
exactly which header to send and where to get one. Both are asserted by tests
rather than left to drift.

## Smoke test against a real server

Phase 1 found two bugs this way that the suite could not, so it was repeated:
a migrated SQLite database, `bootstrap`, a token minted by CLI, `uvicorn` on
:8123, and `curl` speaking JSON-RPC. Verified `initialize`, `tools/list`
returning all eight names, `cmc_whoami`, `cmc_list_vocabulary`, an empty
search, the two error messages, the briefing resource, a call with no token,
a call with a bad token, and that `/api/health` still answers.

**No defects found this time.** Worth noting that the bad-bucket case is caught
by pydantic's `Literal` validation before the hand-written check, so the
hand-written message is unreachable in practice. It stays as a backstop; the
test asserts on the valid values, which both paths name.

## Result

| | Before | After |
|---|---|---|
| Backend tests | 164 | 194 |
| Backend coverage | 92.6% | 92%+ (gate 80%) |
| Frontend tests | 39 | 39 (untouched) |

Green: `ruff check`, `ruff format --check`, the full backend suite, and the
live smoke test.

## Open items for Phase 3

- **Rate limiting is still not implemented.** The design groups it with the MCP
  server, but the limiter must move to the database first for multi-worker
  safety, which the V2.0 quality plan owns. A read-only endpoint behind a
  revocable, expiring token is a bounded risk meanwhile. This is the one piece
  of the design Phase 2 knowingly leaves out.
- `write_mode` is stored and reported by `cmc_whoami`, but nothing enforces it
  yet; it gates the edit tools in Phase 3.
- Phase 3 adds `cmc_post_update` and `cmc_create_item` as open writes, with the
  near-duplicate check and the unreviewed chip. Phase 4 adds the confirm
  handshake and undo.
