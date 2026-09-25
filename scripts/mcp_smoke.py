"""Drive a running tracker's /mcp endpoint the way an agent would, and fail loudly.

Usage: python scripts/mcp_smoke.py http://localhost:8123 cmct_...

Used by scripts/mcp-smoke.sh against a freshly migrated database. It speaks
JSON-RPC over plain HTTP so it tests the real transport, not the test client.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE, TOKEN = sys.argv[1].rstrip("/"), sys.argv[2]
HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
    "Authorization": f"Bearer {TOKEN}",
}
_next_id = 0
failures: list[str] = []


def rpc(method: str, params: dict | None = None, headers: dict | None = None) -> dict:
    global _next_id
    _next_id += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _next_id, "method": method, "params": params or {}})
    request = urllib.request.Request(
        f"{BASE}/mcp/", data=body.encode(), headers=headers or HEADERS, method="POST"
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def call(name: str, headers: dict | None = None, **arguments) -> tuple[bool, str]:
    result = rpc("tools/call", {"name": name, "arguments": arguments}, headers)["result"]
    text = "\n".join(part.get("text", "") for part in result["content"])
    return bool(result.get("isError")), text


def login() -> str:
    """Sign in as the seeded admin and return the session cookie."""
    body = json.dumps(
        {"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}
    ).encode()
    request = urllib.request.Request(
        f"{BASE}/api/auth/login", data=body, method="POST",
        headers={"Content-Type": "application/json", "X-Requested-With": "fetch"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.headers["Set-Cookie"].split(";", 1)[0]


def api(cookie: str, method: str, path: str) -> dict:
    request = urllib.request.Request(
        f"{BASE}{path}", method=method, data=b"" if method == "POST" else None,
        headers={"Cookie": cookie, "X-Requested-With": "fetch"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as failed:
        return json.loads(failed.read())


def check(label: str, condition: bool, detail: str = "") -> None:
    print(f"  {'ok ' if condition else 'FAIL'} {label}")
    if not condition:
        failures.append(f"{label}: {detail[:300]}")


def main() -> int:
    print("initialize")
    check("server answers initialize", "result" in rpc("initialize", {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "smoke", "version": "1"},
    }))

    names = {tool["name"] for tool in rpc("tools/list")["result"]["tools"]}
    print(f"tools/list: {len(names)} tools")
    for expected in (
        "cmc_whoami", "cmc_list_vocabulary", "cmc_search_items", "cmc_get_item",
        "cmc_list_updates", "cmc_get_item_history", "cmc_needs_attention", "cmc_list_activity",
    ):
        check(f"lists {expected}", expected in names)
    check("offers no delete tool", not any("delete" in name for name in names))

    print("reads")
    error, text = call("cmc_whoami")
    check("whoami names the server version", not error and "Server version:" in text, text)
    error, text = call("cmc_list_vocabulary")
    check("vocabulary lists groups", not error and "General Issues" in text, text)
    error, text = call("cmc_search_items", status=["done"])
    check("bad status names the fix", error and 'Did you mean "completed"?' in text, text)
    error, text = call("cmc_search_items", sort="colour")
    check("bad sort names sortable fields", error and "due_on" in text, text)
    error, text = call("cmc_get_item", entry_no=99999)
    check("missing item points at search", error and "cmc_search_items" in text, text)
    error, text = call("cmc_list_activity", entity_type="api_token")
    check("activity filters by record type", not error and "API token" in text, text)

    print("open writes (phase 3)")
    for expected in ("cmc_post_update", "cmc_create_item"):
        check(f"lists {expected}", expected in names)
    new = {"title": "Smoke test extractables scope", "group": "General Issues", "owner_org": "gensci"}
    error, text = call("cmc_create_item", **new, dry_run=True)
    check("create dry run files nothing", not error and "Dry run" in text, text)
    error, text = call("cmc_create_item", **new, idempotency_key="smoke-1")
    check("create files an unreviewed item", not error and "unreviewed" in text, text)
    error, text = call("cmc_create_item", **new, idempotency_key="smoke-1")
    check("idempotent retry replays", not error and "Already filed" in text, text)
    error, text = call("cmc_create_item", **{**new, "title": new["title"] + "."})
    check("near duplicate is refused", error and "confirm_new" in text, text)
    error, text = call("cmc_create_item", **{**new, "group": "Gen2 CMC"})
    check("unknown group names active ones", error and "Gen2 (Process 2.0) CMC" in text, text)
    error, text = call("cmc_create_item", **new, kind="note", status="open", confirm_new=True)
    check("note with a status is refused", error and "Notes have no status" in text, text)
    error, text = call("cmc_post_update", entry_no=1, body="Smoke progress note")
    check("post update appends", not error and "Posted an update on #1" in text, text)
    error, text = call("cmc_get_item_history", entry_no=1)
    check("history marks the agent", not error and "[agent]" in text, text)

    print("edits with confirm (phase 4)")
    for expected in ("cmc_set_status", "cmc_update_item", "cmc_apply_batch"):
        check(f"lists {expected}", expected in names)
    error, preview = call("cmc_set_status", entry_no=1, status="blocked", note="Smoke: waiting")
    token = re.search(r'confirm="(ct_[^"]+)"', preview)
    check("status preview returns a confirm token", not error and bool(token), preview)
    error, text = call("cmc_search_items", status=["blocked"])
    check("preview changed nothing", "No items match" in text, text)
    if token:
        error, text = call("cmc_set_status", entry_no=1, status="cancelled", confirm=token.group(1))
        check("token refuses other arguments", error and "does not match" in text, text)
        error, text = call(
            "cmc_set_status", entry_no=1, status="blocked", note="Smoke: waiting",
            confirm=token.group(1),
        )
        check("confirm applies", not error and text.startswith("Applied"), text)
    error, text = call("cmc_update_item", entry_no=1, title="Renamed by an agent")
    check("identity field is refused", error and "web app" in text, text)
    error, text = call("cmc_create_item", title="t", group="General Issues", owner_org="gensci",
                       prority="p1")
    check("typo is refused, not dropped", error and "priority" in text, text)

    print("export (phase 5)")
    check("lists cmc_export_workbook", "cmc_export_workbook" in names)
    error, text = call("cmc_export_workbook")
    link = re.search(r"https?://\S+/api/export/link/dl_\S+", text)
    check("export returns a link, not bytes", not error and bool(link) and len(text) < 2000, text)
    if link:
        with urllib.request.urlopen(link.group(0), timeout=20) as response:
            body = response.read()
        check("the link downloads an xlsx with no credential", body[:2] == b"PK", str(body[:20]))
        try:
            urllib.request.urlopen(link.group(0)[:-1] + "x", timeout=20)
            check("a tampered link is refused", False, "download succeeded")
        except urllib.error.HTTPError as refused:
            check("a tampered link is refused", refused.code == 404, str(refused.code))
    error, text = call("cmc_export_workbook", kind="period_report")
    check("period report is refused as not built", error and "not available yet" in text, text)

    print("undo through a person's session (phase 4)")
    session = login()
    history = api(session, "GET", "/api/items/1/history")["data"]
    change = next((e for e in history if e["action"] == "status_changed"), None)
    check("agent status change is undoable", bool(change and change["can_undo"]), str(change))
    if change:
        undone = api(session, "POST", f"/api/activity/{change['id']}/revert")
        check("undo reverts it", undone.get("data", {}).get("action") == "reverted", str(undone))
        item = api(session, "GET", "/api/items/1")["data"]
        check("status is back", item["status"] != "blocked", str(item["status"]))

    print("auth")
    anonymous = {key: value for key, value in HEADERS.items() if key != "Authorization"}
    error, text = call("cmc_whoami", headers=anonymous)
    check("no token is refused with instructions", error and "Bearer cmct_" in text, text)
    error, text = call("cmc_whoami", headers={**HEADERS, "Authorization": "Bearer cmct_x"})
    check("bad token is refused", error and "not recognised" in text, text)

    print("REST is read-only to tokens")
    request = urllib.request.Request(
        f"{BASE}/api/items",
        data=json.dumps({"title": "x", "group": "General Issues", "owner_org": "gensci"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=20)
        check("a write token cannot POST to /api", False, "request succeeded")
    except urllib.error.HTTPError as refused:
        check("a write token cannot POST to /api", refused.code == 403, str(refused.code))

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
