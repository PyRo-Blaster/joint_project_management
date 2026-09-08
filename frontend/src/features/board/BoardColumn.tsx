import { useDroppable } from "@dnd-kit/core";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ItemOut } from "@/lib/api/types";
import type { Status } from "@/lib/constants";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/cn";
import { BoardCard } from "./BoardCard";

export function BoardColumn({
  status,
  items,
  collapsed,
  onToggle,
}: {
  status: Status;
  items: ItemOut[];
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-72 shrink-0 flex-col rounded-lg border border-border bg-surface-2/40",
        isOver && "ring-2 ring-ring",
      )}
    >
      <button
        onClick={onToggle}
        className="flex items-center justify-between gap-2 px-3 py-2 text-sm font-medium"
      >
        <span className="flex items-center gap-1.5">
          <span
            className="size-2 rounded-full"
            style={{ backgroundColor: `var(--status-${status})` }}
          />
          {STATUS_LABELS[status]}
          <span className="tabular-nums text-fg-subtle">{items.length}</span>
        </span>
        {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
      </button>
      {!collapsed && (
        <div className="flex flex-1 flex-col gap-2 p-2 pt-0">
          {items.map((item) => (
            <BoardCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
