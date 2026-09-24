"""Drive a running tracker's /mcp endpoint the way an agent would, and fail loudly.

Usage: python scripts/mcp_smoke.py http://localhost:8123 cmct_...

Used by scripts/mcp-smoke.sh against a freshly migrated database. It speaks
JSON-RPC over plain HTTP so it tests the real transport, not the test client.
"""

import json
import sys
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

    print("auth")
    anonymous = {key: value for key, value in HEADERS.items() if key != "Authorization"}
    error, text = call("cmc_whoami", headers=anonymous)
    check("no token is refused with instructions", error and "Bearer cmct_" in text, text)
    error, text = call("cmc_whoami", headers={**HEADERS, "Authorization": "Bearer cmct_x"})
    check("bad token is refused", error and "revoked" in text, text)

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
