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

Writing comes in two kinds. Additive tools apply at once: cmc_post_update appends
a dated note and cmc_create_item files a new item, flagged until a person reviews
it. Edit tools (cmc_set_status, cmc_update_item, cmc_apply_batch) take two calls:
the first changes nothing and returns a diff and a confirm token; show the person
the diff, and only when they agree, call again with the token. Title, group,
owner and kind cannot be edited here. No tool deletes anything, and none ever will.

cmc_export_workbook returns a short-lived download link for a person, not the file.\
"""


def build_mcp_server() -> MCPServer:
    from app.mcp import prompts, tools_edit, tools_export, tools_read, tools_write
    from app.mcp.strict_args import StrictArguments

    strict = StrictArguments()
    server = MCPServer(
        name="joint-cmc-tracker",
        title="Joint CMC Tracker",
        version=__version__,
        instructions=INSTRUCTIONS,
        middleware=[strict],
    )
    strict.server = server
    tools_read.register(server)
    tools_write.register(server)
    tools_edit.register(server)
    tools_export.register(server)
    prompts.register(server)
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
