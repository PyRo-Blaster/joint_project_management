"""Turn a bad value into an error that names the good ones (design section 8).

An agent that is told the valid values fixes its own call; one that is told
"invalid input" guesses again. Every check here returns the canonical value on
success, so callers can pass user text straight through.
"""

from collections.abc import Sequence
from difflib import get_close_matches

from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.orm import Session

from app.constants import KINDS, OWNER_ORGS, PRIORITIES, STATUSES
from app.services.vocab import list_terms

# Words people actually type for a status. Checked before fuzzy matching, because
# "done" is nowhere near "completed" by edit distance.
STATUS_SYNONYMS = {
    "done": "completed",
    "closed": "completed",
    "complete": "completed",
    "finished": "completed",
    "resolved": "completed",
    "wip": "in_progress",
    "in progress": "in_progress",
    "ongoing": "in_progress",
    "started": "in_progress",
    "hold": "on_hold",
    "on hold": "on_hold",
    "paused": "on_hold",
    "canceled": "cancelled",
    "dropped": "cancelled",
    "new": "open",
    "todo": "open",
}
OWNER_SYNONYMS = {"both": "joint", "gensci/yarrow": "joint", "yarrow/gensci": "joint"}


def _suggest(value: str, valid: Sequence[str], synonyms: dict[str, str]) -> str | None:
    if value in synonyms:
        return synonyms[value]
    close = get_close_matches(value, list(valid), n=1, cutoff=0.6)
    return close[0] if close else None


def check_choice(
    raw: str, valid: Sequence[str], noun: str, synonyms: dict[str, str] | None = None
) -> str:
    value = (raw or "").strip().lower()
    if value in valid:
        return value
    hint = _suggest(value, valid, synonyms or {})
    message = f'"{raw}" is not a {noun}. Valid: {", ".join(valid)}.'
    if hint:
        message += f' Did you mean "{hint}"?'
    raise ToolError(message)


def check_status(raw: str) -> str:
    return check_choice(raw, STATUSES, "status", STATUS_SYNONYMS)


def check_priority(raw: str) -> str:
    return check_choice(raw, PRIORITIES, "priority")


def check_owner_org(raw: str) -> str:
    return check_choice(raw, OWNER_ORGS, "owner organisation", OWNER_SYNONYMS)


def check_kind(raw: str) -> str:
    return check_choice(raw, KINDS, "kind")


def check_term(
    db: Session, program_id: int, field: str, raw: str, *, active_only: bool = False
) -> str:
    """Match a vocabulary term case-insensitively and return its canonical spelling.

    Filtering accepts inactive terms too, because old items still carry them.
    Creating or editing accepts active terms only.
    """
    terms = [
        term for term in list_terms(db, program_id, field) if term.is_active or not active_only
    ]
    by_lower = {term.value.lower(): term.value for term in terms}
    value = (raw or "").strip()
    if value.lower() in by_lower:
        return by_lower[value.lower()]

    active = [term.value for term in terms if term.is_active]
    label = field.capitalize()
    state = "an active" if active_only else "a known"
    message = (
        f'{label} "{raw}" is not {state} term. Active {field}s: {", ".join(active)}. '
        "An admin adds terms in the web UI."
    )
    hint = get_close_matches(value.lower(), list(by_lower), n=1, cutoff=0.6)
    if hint:
        message += f' Did you mean "{by_lower[hint[0]]}"?'
    raise ToolError(message)


def check_many(values: Sequence[str] | None, check) -> tuple[str, ...]:
    return tuple(check(value) for value in (values or ()))
