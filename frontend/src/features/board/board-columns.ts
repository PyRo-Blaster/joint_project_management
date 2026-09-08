import type { ItemOut } from "@/lib/api/types";
import type { Status } from "@/lib/constants";

/** Board columns, in order; notes are excluded upstream (kind = action only). */
export const BOARD_STATUSES: Status[] = [
  "open",
  "in_progress",
  "blocked",
  "on_hold",
  "completed",
  "cancelled",
];

const PRIORITY_RANK: Record<string, number> = { p1: 0, p2: 1, p3: 2 };

function priorityRank(p: string | null): number {
  return p ? (PRIORITY_RANK[p] ?? 3) : 3;
}

function dueRank(due: string | null): number {
  return due ? new Date(`${due}T00:00:00`).getTime() : Number.POSITIVE_INFINITY;
}

/** Cards ordered by priority (P1 first) then due date (earliest first, undated last). */
export function orderCards(items: ItemOut[]): ItemOut[] {
  return [...items].sort(
    (a, b) =>
      priorityRank(a.priority) - priorityRank(b.priority) || dueRank(a.due_on) - dueRank(b.due_on),
  );
}

export type BoardColumns = Record<Status, ItemOut[]>;

/** Group action items by status into ordered columns. Unknown statuses are ignored. */
export function groupIntoColumns(items: ItemOut[]): BoardColumns {
  const columns = Object.fromEntries(
    BOARD_STATUSES.map((s) => [s, [] as ItemOut[]]),
  ) as BoardColumns;
  for (const item of items) {
    if (item.status && item.status in columns) columns[item.status as Status].push(item);
  }
  for (const s of BOARD_STATUSES) columns[s] = orderCards(columns[s]);
  return columns;
}
