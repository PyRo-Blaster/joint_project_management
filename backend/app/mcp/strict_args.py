"""Refuse arguments a tool does not take, instead of silently dropping them.

The SDK ignores unknown arguments. For a tracker that is dangerous in two ways:
an agent that sends ``cmc_update_item(title=...)`` is told nothing and believes
it renamed the item, and a typo such as ``prority="p1"`` on ``cmc_create_item``
files the item without a priority. This middleware sees the raw ``tools/call``
arguments before validation and refuses anything the tool's schema does not
list, naming the valid arguments. Identity fields get their own message
(design 7.2): they are changed in the web app, by a person.
"""

from difflib import get_close_matches
from typing import Any

from mcp.server.mcpserver import MCPServer

IDENTITY_FIELDS = ("title", "group", "owner_org", "kind", "entry_no")
IDENTITY_MESSAGE = (
    "{fields} cannot be changed by an agent: title, group, owner organisation and kind are "
    "the item's identity and its accountability between the two companies. A person "
    "changes them in the web app."
)
# The per-change keys cmc_apply_batch accepts; kept beside the tool's model.
BATCH_CHANGE_KEYS = frozenset(
    {
        "entry_no",
        "status",
        "due_on",
        "priority",
        "category",
        "assignee_id",
        "details",
        "notes_risks",
        "file_path",
        "post",
        "occurred_on",
    }
)


def _refusal(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": True}


def _unknown_message(tool: str, unknown: list[str], valid: set[str]) -> str:
    hints = []
    for name in unknown:
        close = get_close_matches(name, sorted(valid), n=1, cutoff=0.7)
        if close:
            hints.append(f'"{name}" — did you mean "{close[0]}"?')
    message = (
        f"{tool} does not take {', '.join(repr(n) for n in unknown)}. "
        f"Its arguments are: {', '.join(sorted(valid))}."
    )
    return message + (" " + " ".join(hints) if hints else "")


def _check(tool: str, arguments: dict, valid: set[str]) -> str | None:
    unknown = sorted(set(arguments) - valid)
    if not unknown:
        return None
    identity = [name for name in unknown if name in IDENTITY_FIELDS and name != "entry_no"]
    if identity and tool in {"cmc_update_item", "cmc_set_status", "cmc_apply_batch"}:
        return IDENTITY_MESSAGE.format(fields=", ".join(identity))
    return _unknown_message(tool, unknown, valid)


class StrictArguments:
    """ServerMiddleware: refuse unknown tool arguments with an actionable message."""

    def __init__(self) -> None:
        self.server: MCPServer | None = None
        self._allowed: dict[str, set[str]] | None = None

    async def _allowed_arguments(self) -> dict[str, set[str]]:
        if self._allowed is None:
            assert self.server is not None, "attach the server before serving"
            self._allowed = {
                tool.name: set(tool.input_schema.get("properties", {}))
                for tool in await self.server.list_tools()
            }
        return self._allowed

    async def __call__(self, ctx, call_next):
        if ctx.method != "tools/call":
            return await call_next(ctx)
        params = ctx.params or {}
        tool = params.get("name")
        arguments = params.get("arguments") or {}
        allowed = await self._allowed_arguments()
        if tool not in allowed or not isinstance(arguments, dict):
            return await call_next(ctx)

        problem = _check(tool, arguments, allowed[tool])
        if problem is None and tool == "cmc_apply_batch":
            for index, change in enumerate(arguments.get("changes") or []):
                if isinstance(change, dict):
                    found = _check(tool, change, set(BATCH_CHANGE_KEYS))
                    if found:
                        problem = f"Change {index + 1}: {found}"
                        break
        return _refusal(problem) if problem else await call_next(ctx)
