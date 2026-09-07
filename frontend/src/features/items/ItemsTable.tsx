import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { ItemOut, UserBrief } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { COLUMNS } from "./columns";

interface Props {
  items: ItemOut[];
  usersById: Map<number, UserBrief>;
  visible: Set<string>;
  sort: string;
  direction: "asc" | "desc";
  onSort: (sortKey: string) => void;
  onOpen: (id: number) => void;
  selectedId: number | null;
}

export function ItemsTable({
  items,
  usersById,
  visible,
  sort,
  direction,
  onSort,
  onOpen,
  selectedId,
}: Props) {
  const cols = COLUMNS.filter((c) => visible.has(c.id));
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border">
            {cols.map((col) => (
              <th
                key={col.id}
                scope="col"
                className={cn(
                  "px-4 py-2.5 text-left font-medium text-fg-muted",
                  col.align === "right" && "text-right",
                )}
              >
                {col.sortKey ? (
                  <button
                    type="button"
                    onClick={() => onSort(col.sortKey!)}
                    className="inline-flex items-center gap-1 hover:text-fg"
                  >
                    {col.header}
                    <SortIcon active={sort === col.sortKey} direction={direction} />
                  </button>
                ) : (
                  col.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              onClick={() => onOpen(item.id)}
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onOpen(item.id)}
              aria-selected={selectedId === item.id}
              className={cn(
                "cursor-pointer border-b border-border/60 transition-colors last:border-0 hover:bg-surface-2 focus:bg-surface-2 focus:outline-none",
                selectedId === item.id && "bg-accent-weak/40",
              )}
            >
              {cols.map((col) => (
                <td
                  key={col.id}
                  className={cn("px-4 py-3 align-middle", col.align === "right" && "text-right")}
                >
                  {col.cell(item, { usersById })}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) return <ChevronsUpDown className="size-3.5 opacity-40" aria-hidden />;
  return direction === "asc" ? (
    <ArrowUp className="size-3.5" aria-hidden />
  ) : (
    <ArrowDown className="size-3.5" aria-hidden />
  );
}
