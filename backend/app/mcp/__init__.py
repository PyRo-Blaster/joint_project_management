"""The MCP server: a sibling of app/api, mounted into the same FastAPI app."""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette

from app import __version__
from app.config import Settings

INSTRUCTIONS = """\
The joint CMC action tracker for programme GS098, shared by GenSci and Yarrow.

Items are numbered; people refer to them as "#42", and every tool takes that
entry number. An item is either an action (it has a status) or a note (a
recorded decision, no status). Progress is recorded as dated timeline updates
rather than by editing history.

Call cmc_list_vocabulary before filtering on or quoting a group or category:
the valid values are programme-specific. Read cmc://program/briefing once for
the conventions both teams follow.

This server is read-only. Nothing here changes the tracker.\
"""


def build_mcp_server() -> MCPServer:
    from app.mcp import tools_read

    server = MCPServer(
        name="joint-cmc-tracker",
        title="Joint CMC Tracker",
        version=__version__,
        instructions=INSTRUCTIONS,
    )
    tools_read.register(server)
    return server


def mcp_asgi_app(settings: Settings) -> Starlette:
    """Streamable HTTP, stateless, to be mounted under /mcp by the caller.

    Host checking stays off unless MCP_ALLOWED_HOSTS is set: this endpoint takes
    no ambient credential (bearer tokens only, never the session cookie), so DNS
    rebinding has nothing to steal.
    """
    hosts = [host.strip() for host in settings.mcp_allowed_hosts.split(",") if host.strip()]
    return build_mcp_server().streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=bool(hosts),
            allowed_hosts=hosts,
        ),
    )
