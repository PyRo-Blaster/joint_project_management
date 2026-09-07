export const CSRF_HEADER = "X-Requested-With";
export const CSRF_VALUE = "fetch";
export const SESSION_EXPIRED_EVENT = "cmc:session-expired";

export const STATUSES = [
  "open",
  "in_progress",
  "blocked",
  "on_hold",
  "completed",
  "cancelled",
] as const;

export const PRIORITIES = ["p1", "p2", "p3"] as const;
export const OWNER_ORGS = ["gensci", "yarrow", "joint"] as const;
export const KINDS = ["action", "note"] as const;

export const STATUS_LABELS: Record<(typeof STATUSES)[number], string> = {
  open: "Open",
  in_progress: "In progress",
  blocked: "Blocked",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const PRIORITY_LABELS: Record<(typeof PRIORITIES)[number], string> = {
  p1: "P1",
  p2: "P2",
  p3: "P3",
};

export const OWNER_LABELS: Record<(typeof OWNER_ORGS)[number], string> = {
  gensci: "GenSci",
  yarrow: "Yarrow",
  joint: "GenSci/Yarrow",
};

export const KIND_LABELS: Record<(typeof KINDS)[number], string> = {
  action: "Action",
  note: "Note",
};

export const MIN_PASSWORD_LENGTH = 10;

export const ITEM_COLUMNS = [
  { id: "entry_no", label: "#", defaultVisible: true },
  { id: "title", label: "Title", defaultVisible: true },
  { id: "status", label: "Status", defaultVisible: true },
  { id: "priority", label: "Priority", defaultVisible: true },
  { id: "group", label: "Group", defaultVisible: true },
  { id: "category", label: "Category", defaultVisible: false },
  { id: "owner_org", label: "Owner", defaultVisible: true },
  { id: "due_on", label: "Due", defaultVisible: true },
  { id: "last_update_on", label: "Last update", defaultVisible: true },
  { id: "kind", label: "Kind", defaultVisible: false },
] as const;

export type ItemColumnId = (typeof ITEM_COLUMNS)[number]["id"];
