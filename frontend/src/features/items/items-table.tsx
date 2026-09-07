import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import type { ItemOut } from "@/lib/api/types";
import type { ItemColumnId } from "@/lib/constants";
import { ITEM_COLUMNS, KIND_LABELS } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { OwnerBadge, PriorityBadge, StatusBadge } from "@/features/items/status-badge";

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) return <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />;
  return direction === "asc" ? (
    <ArrowUp className="h-3.5 w-3.5" />
  ) : (
    <ArrowDown className="h-3.5 w-3.5" />
  );
}

function cellValue(item: ItemOut, column: ItemColumnId) {
  switch (column) {
    case "entry_no":
      return <span className="font-mono text-ink-muted">{item.entry_no}</span>;
    case "title":
      return (
        <div className="max-w-md">
          <div className="font-medium text-ink">{item.title}</div>
          {item.details ? (
            <div className="mt-0.5 line-clamp-1 text-xs text-ink-muted">{item.details}</div>
          ) : null}
        </div>
      );
    case "status":
      return <StatusBadge status={item.status} />;
    case "priority":
      return <PriorityBadge priority={item.priority} />;
    case "group":
      return item.group;
    case "category":
      return item.category ?? "—";
    case "owner_org":
      return <OwnerBadge owner={item.owner_org} />;
    case "due_on":
      return formatDate(item.due_on);
    case "last_update_on":
      return formatDate(item.last_update_on);
    case "kind":
      return KIND_LABELS[item.kind as keyof typeof KIND_LABELS] ?? item.kind;
    default:
      return "—";
  }
}

export function ItemsTable({
  items,
  visibleColumns,
  sort,
  direction,
  selectedId,
  onSort,
  onRowClick,
}: {
  items: ItemOut[];
  visibleColumns: ItemColumnId[];
  sort: string;
  direction: "asc" | "desc";
  selectedId?: number | null;
  onSort: (column: string) => void;
  onRowClick: (item: ItemOut) => void;
}) {
  const columns = ITEM_COLUMNS.filter((c) => visibleColumns.includes(c.id));

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface-raised shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead className="bg-surface-muted/80 text-xs uppercase tracking-wide text-ink-muted">
            <tr>
              {columns.map((col) => {
                const sortable = [
                  "entry_no",
                  "title",
                  "status",
                  "priority",
                  "group",
                  "due_on",
                  "last_update_on",
                  "owner_org",
                  "kind",
                ].includes(col.id);
                return (
                  <th key={col.id} className="whitespace-nowrap px-4 py-3 font-medium">
                    {sortable ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 hover:text-ink"
                        onClick={() => onSort(col.id)}
                      >
                        {col.label}
                        <SortIcon active={sort === col.id} direction={direction} />
                      </button>
                    ) : (
                      col.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-ink-muted">
                  No items match these filters.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr
                  key={item.id}
                  className={cn(
                    "cursor-pointer border-t border-line/80 transition hover:bg-cyan-50/40",
                    selectedId === item.id && "bg-cyan-50/70",
                  )}
                  onClick={() => onRowClick(item)}
                >
                  {columns.map((col) => (
                    <td key={col.id} className="px-4 py-3.5 align-top">
                      {cellValue(item, col.id)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
