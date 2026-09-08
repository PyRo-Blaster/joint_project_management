export const STATUSES = [
  "open",
  "in_progress",
  "blocked",
  "on_hold",
  "completed",
  "cancelled",
] as const;
export const CLOSED_STATUSES = ["completed", "cancelled"] as const;
export const PRIORITIES = ["p1", "p2", "p3"] as const;
export const OWNER_ORGS = ["gensci", "yarrow", "joint"] as const;
export const ORGS = ["gensci", "yarrow"] as const;
export const ROLES = ["admin", "member"] as const;
export const KINDS = ["action", "note"] as const;

export type Status = (typeof STATUSES)[number];
export type Priority = (typeof PRIORITIES)[number];
export type OwnerOrg = (typeof OWNER_ORGS)[number];
export type Org = (typeof ORGS)[number];
export type Role = (typeof ROLES)[number];
export type Kind = (typeof KINDS)[number];
