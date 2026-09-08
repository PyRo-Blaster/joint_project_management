import { useDraggable } from "@dnd-kit/core";
import { useNavigate } from "react-router-dom";
import { DueDate } from "@/components/domain/DueDate";
import { OwnerBadge } from "@/components/domain/OwnerBadge";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import type { ItemOut } from "@/lib/api/types";
import { cn } from "@/lib/cn";

export function BoardCard({ item }: { item: ItemOut }) {
  const navigate = useNavigate();
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: item.id });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={() => navigate(`/items?selected=${item.id}`)}
      className={cn(
        "cursor-grab rounded-md border border-border bg-surface p-3 shadow-sm active:cursor-grabbing",
        isDragging && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs tabular-nums text-fg-subtle">#{item.entry_no}</span>
        <PriorityBadge priority={item.priority} />
      </div>
      <p className="mt-1 line-clamp-2 text-sm font-medium">{item.title}</p>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs">
        <OwnerBadge owner={item.owner_org} />
        <DueDate dueOn={item.due_on} />
      </div>
    </div>
  );
}
