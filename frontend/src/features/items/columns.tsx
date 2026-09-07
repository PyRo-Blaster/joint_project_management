import type { ReactNode } from "react";
import { DueDate } from "@/components/domain/DueDate";
import { KindBadge } from "@/components/domain/KindBadge";
import { OwnerBadge } from "@/components/domain/OwnerBadge";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { StatusBadge } from "@/components/domain/StatusBadge";
import type { ItemOut, UserBrief } from "@/lib/api/types";

export interface CellContext {
  usersById: Map<number, UserBrief>;
}

export interface ColumnDef {
  id: string;
  header: string;
  sortKey?: string; // backend sort field; omit for display-only columns
  defaultVisible: boolean;
  align?: "right";
  cell: (item: ItemOut, ctx: CellContext) => ReactNode;
}

const dash = <span className="text-fg-subtle">—</span>;

export const COLUMNS: ColumnDef[] = [
  {
    id: "entry_no",
    header: "#",
    sortKey: "entry_no",
    defaultVisible: true,
    align: "right",
    cell: (i) => <span className="tabular-nums text-fg-muted">{i.entry_no}</span>,
  },
  {
    id: "title",
    header: "Title",
    sortKey: "title",
    defaultVisible: true,
    cell: (i) => (
      <span className="flex items-center gap-2">
        <span className="font-medium text-fg">{i.title}</span>
        {i.kind === "note" && <KindBadge kind="note" />}
      </span>
    ),
  },
  {
    id: "status",
    header: "Status",
    sortKey: "status",
    defaultVisible: true,
    cell: (i) => <StatusBadge status={i.status} />,
  },
  {
    id: "priority",
    header: "Priority",
    sortKey: "priority",
    defaultVisible: true,
    cell: (i) => <PriorityBadge priority={i.priority} />,
  },
  {
    id: "owner_org",
    header: "Owner",
    sortKey: "owner_org",
    defaultVisible: true,
    cell: (i) => <OwnerBadge owner={i.owner_org} />,
  },
  { id: "category", header: "Category", defaultVisible: false, cell: (i) => i.category ?? dash },
  {
    id: "group",
    header: "Group",
    sortKey: "group",
    defaultVisible: false,
    cell: (i) => <span className="text-fg-muted">{i.group}</span>,
  },
  {
    id: "assignee",
    header: "Assignee",
    defaultVisible: false,
    cell: (i, ctx) =>
      i.assignee_id == null
        ? dash
        : (ctx.usersById.get(i.assignee_id)?.name ?? `#${i.assignee_id}`),
  },
  {
    id: "due_on",
    header: "Due",
    sortKey: "due_on",
    defaultVisible: true,
    cell: (i) => <DueDate dueOn={i.due_on} />,
  },
  {
    id: "updated",
    header: "Updated",
    sortKey: "updated_at",
    defaultVisible: true,
    cell: (i) => <RelativeTime iso={i.updated_at} />,
  },
];

export const DEFAULT_VISIBLE: string[] = COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id);
