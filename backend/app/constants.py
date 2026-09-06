"""Controlled values shared by models, schemas, services, and the importer."""

from typing import Literal, get_args

Org = Literal["gensci", "yarrow"]
OwnerOrg = Literal["gensci", "yarrow", "joint"]
Role = Literal["admin", "member"]
Kind = Literal["action", "note"]
Status = Literal["open", "in_progress", "blocked", "on_hold", "completed", "cancelled"]
Priority = Literal["p1", "p2", "p3"]
VocabField = Literal["group", "category"]
InvitePurpose = Literal["invite", "reset"]
EntityType = Literal["item", "user", "invitation", "vocab_term", "import"]
AuditAction = Literal[
    "created",
    "updated",
    "deleted",
    "restored",
    "status_changed",
    "update_posted",
    "update_edited",
    "update_deleted",
    "role_changed",
    "deactivated",
    "reactivated",
    "invited",
    "revoked",
    "reset_link_issued",
    "imported",
]

ORGS: tuple[str, ...] = get_args(Org)
OWNER_ORGS: tuple[str, ...] = get_args(OwnerOrg)
ROLES: tuple[str, ...] = get_args(Role)
KINDS: tuple[str, ...] = get_args(Kind)
STATUSES: tuple[str, ...] = get_args(Status)
CLOSED_STATUSES: tuple[str, ...] = ("completed", "cancelled")
STALE_CANDIDATE_STATUSES: tuple[str, ...] = ("in_progress", "blocked")
PRIORITIES: tuple[str, ...] = get_args(Priority)
VOCAB_FIELDS: tuple[str, ...] = get_args(VocabField)
INVITE_PURPOSES: tuple[str, ...] = get_args(InvitePurpose)
ENTITY_TYPES: tuple[str, ...] = get_args(EntityType)
AUDIT_ACTIONS: tuple[str, ...] = get_args(AuditAction)

SESSION_COOKIE = "cmc_session"
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "fetch"
REQUEST_ID_HEADER = "X-Request-ID"

MIN_PASSWORD_LENGTH = 10
TITLE_MAX_LENGTH = 500
MAX_PAGE_LIMIT = 200
MAX_IMPORT_BYTES = 5 * 1024 * 1024

STATUS_LABELS = {
    "open": "Open",
    "in_progress": "In progress",
    "blocked": "Blocked",
    "on_hold": "On hold",
    "completed": "Completed",
    "cancelled": "Cancelled",
}
OWNER_LABELS = {"gensci": "GenSci", "yarrow": "Yarrow", "joint": "GenSci/Yarrow"}
PRIORITY_LABELS = {"p1": "P1", "p2": "P2", "p3": "P3"}

SEED_GROUPS: tuple[str, ...] = ("General Issues", "Gen1 (existing) CMC", "Gen2 (Process 2.0) CMC")
SEED_CATEGORIES: tuple[str, ...] = (
    "QA",
    "QC",
    "AS",
    "AS/QC",
    "DS",
    "DP",
    "USPD",
    "Legal",
    "Non-clinical",
)
OWNER_ALIASES = {
    "gensci": "gensci",
    "yarrow": "yarrow",
    "gensci/yarrow": "joint",
    "yarrow/gensci": "joint",
    "joint": "joint",
}
STATUS_ALIASES = {
    "open": "open",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "blocked": "blocked",
    "on hold": "on_hold",
    "on_hold": "on_hold",
    "completed": "completed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}
