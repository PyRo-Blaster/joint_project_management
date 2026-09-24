"""Prompt templates that turn a common chore into a reviewed tool sequence (design 8)."""

from mcp.server.mcpserver import MCPServer


def register(server: MCPServer) -> None:
    @server.prompt(
        name="weekly_update",
        title="Draft this week's updates",
        description=(
            "Drafts one progress note per open item in a group from the last week's "
            "activity, for a person to review before anything is posted."
        ),
    )
    def weekly_update(group: str) -> str:
        return f"""Draft this week's progress updates for the group "{group}".

1. Call cmc_list_vocabulary and confirm "{group}" is a real group; if not, stop and
   say which groups exist.
2. Call cmc_search_items with group=["{group}"] and status=["open","in_progress",
   "blocked","on_hold"] to list the open items.
3. Call cmc_list_activity with since set to seven days ago, and cmc_list_updates for
   any item that moved, to see what actually happened.
4. For each item with real news, draft one or two plain sentences. Skip items with
   nothing new rather than inventing progress.
5. Show me every draft next to its entry number and wait. Post nothing until I say
   which to send; then post each with cmc_post_update, one call per item.

Never change a status, due date or any other field in this task: only post updates."""
