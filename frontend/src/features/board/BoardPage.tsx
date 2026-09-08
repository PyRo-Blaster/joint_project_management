import { useMemo } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useSearchParams } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterBar } from "@/features/items/FilterBar";
import { ViewToggle } from "@/features/items/ViewToggle";
import { ItemDetailSheet } from "@/features/item-detail/ItemDetailSheet";
import { filtersToSearchParams, parseFilters, type ItemFilters } from "@/features/items/filters";
import { useToast } from "@/lib/toast";
import { BOARD_STATUSES } from "./board-columns";
import { BoardColumn } from "./BoardColumn";
import { useBoardColumns } from "./useBoardColumns";
import { useCollapsedColumns } from "./board-prefs";
import { useMoveItemStatus } from "./useMoveItemStatus";

export function BoardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const board = useBoardColumns(filters);
  const { collapsed, toggle } = useCollapsedColumns();
  const move = useMoveItemStatus();
  const { toast } = useToast();
  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor));

  function apply(next: Partial<ItemFilters>) {
    const params = filtersToSearchParams({ ...filters, ...next, page: 1 });
    const selected = searchParams.get("selected");
    if (selected) params.set("selected", selected);
    setSearchParams(params);
  }

  function onDragEnd(event: DragEndEvent) {
    const id = Number(event.active.id);
    const target = event.over?.id as string | undefined;
    if (!target || !BOARD_STATUSES.includes(target as never)) return;
    const columns = board.columns;
    const from = BOARD_STATUSES.find((s) => columns[s].some((i) => i.id === id));
    if (!from || from === target) return;
    move.mutate(
      { id, status: target as never },
      { onError: () => toast({ title: "Could not move the card", variant: "error" }) },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Board</h1>
        <ViewToggle />
      </div>
      <FilterBar filters={filters} onChange={apply} />
      {board.isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <DndContext sensors={sensors} onDragEnd={onDragEnd}>
          <div className="flex gap-3 overflow-x-auto pb-4">
            {BOARD_STATUSES.map((status) => (
              <BoardColumn
                key={status}
                status={status}
                items={board.columns[status]}
                collapsed={collapsed.has(status)}
                onToggle={() => toggle(status)}
              />
            ))}
          </div>
        </DndContext>
      )}
      <ItemDetailSheet />
    </div>
  );
}
