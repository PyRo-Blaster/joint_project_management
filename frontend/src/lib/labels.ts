import type { Kind, OwnerOrg, Priority, Status } from "./constants";

export const STATUS_LABELS: Record<Status, string> = {
  open: "Open",
  in_progress: "In progress",
  blocked: "Blocked",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const OWNER_LABELS: Record<OwnerOrg, string> = {
  gensci: "GenSci",
  yarrow: "Yarrow",
  joint: "GenSci/Yarrow",
};

export const ORG_LABELS: Record<string, string> = { gensci: "GenSci", yarrow: "Yarrow" };
export const PRIORITY_LABELS: Record<Priority, string> = { p1: "P1", p2: "P2", p3: "P3" };
export const KIND_LABELS: Record<Kind, string> = { action: "Action", note: "Note" };

/** Human label for a nullable status, treating null as a note. */
export function statusLabel(status: string | null): string {
  if (!status) return "Note";
  return STATUS_LABELS[status as Status] ?? status;
}
