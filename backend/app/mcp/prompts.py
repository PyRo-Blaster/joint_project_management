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

    @server.prompt(
        name="meeting_minutes_to_changes",
        title="Turn meeting minutes into tracker changes",
        description=(
            "Reads pasted minutes and prepares one cmc_apply_batch preview of every status "
            "change, date change and note they imply, for the person to confirm."
        ),
    )
    def meeting_minutes_to_changes(minutes: str) -> str:
        return f"""Turn these meeting minutes into changes to the tracker.

<minutes>
{minutes}
</minutes>

1. Call cmc_list_vocabulary for the valid statuses and priorities.
2. For every item the minutes mention by number ("#42") or unmistakably by title,
   call cmc_get_item to see its current state. Use cmc_search_items to find items
   mentioned only by title; if a match is not unmistakable, list it as a question
   instead of guessing.
3. Build one cmc_apply_batch call: one entry per item, with a status, due_on or
   priority only where the minutes actually decided one, and a post quoting the
   decision in one or two sentences so the timeline shows why.
4. Call cmc_apply_batch WITHOUT confirm. It changes nothing and returns a diff and
   a confirm token. Show me that diff, plus any open questions, and wait.
5. Only when I say yes, call cmc_apply_batch again with the same changes and the
   confirm token. If it reports that an item changed in the meantime, re-read it
   and prepare a fresh preview; do not retry blindly.

New actions agreed in the meeting are separate: list them for me, and file each
with cmc_create_item only after I confirm, since it refuses near-duplicates.
Never try to change a title, group, owner or kind; those are changed in the web
app."""
