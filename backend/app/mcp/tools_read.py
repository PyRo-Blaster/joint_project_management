"""Read-only tools. Every one is annotated readOnlyHint and changes nothing."""

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import ToolAnnotations
from sqlalchemy.orm import Session

from app.mcp.runtime import Caller, call_tool
from app.models import Program

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)


def register(server: MCPServer) -> None:
    @server.tool(
        name="cmc_whoami",
        description=(
            "Who this token acts as, what it may do, and which programme it reaches. "
            "Call this first if you are unsure whether you can write."
        ),
        annotations=READ_ONLY,
    )
    async def cmc_whoami(ctx: Context) -> str:
        return await call_tool(ctx, _whoami)


def _whoami(db: Session, caller: Caller, program: Program) -> str:
    scopes = ", ".join(sorted(caller.token.scope_set))
    may_write = "write" in caller.token.scope_set
    tail = (
        "; the write tools arrive in a later release."
        if may_write
        else ", and this token has no write scope in any case."
    )
    return "\n".join(
        [
            f"Acting as {caller.user.name} <{caller.user.email}>",
            f"Organisation: {caller.user.org} · Role: {caller.user.role}",
            f"Token: {caller.token.name} ({caller.token.prefix}) · Scopes: {scopes}",
            f"Write mode: {caller.token.write_mode}",
            f"Programme: {program.code} — {program.name}",
            "",
            f"This server is read-only today{tail}",
        ]
    )
