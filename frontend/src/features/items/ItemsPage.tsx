import { useMemo } from "react";
import { ListChecks } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { ColumnChooser } from "./ColumnChooser";
import { FilterBar } from "./FilterBar";
import { filtersToSearchParams, parseFilters, type ItemFilters } from "./filters";
import { ItemsTable } from "./ItemsTable";
import { Pagination } from "./Pagination";
import { useColumnVisibility } from "./useColumnVisibility";
import { useItems } from "./useItems";
import { useUsers } from "./useUsers";

export function ItemsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const items = useItems(filters);
  const { byId } = useUsers();
  const { visible, toggle, columns } = useColumnVisibility();

  function apply(next: Partial<ItemFilters>) {
    const merged = { ...filters, ...next };
    if (!("page" in next)) merged.page = 1; // any content/sort change returns to page 1
    const params = filtersToSearchParams(merged);
    const selected = searchParams.get("selected");
    if (selected) params.set("selected", selected);
    setSearchParams(params);
  }

  function onSort(sortKey: string) {
    const direction = filters.sort === sortKey && filters.direction === "asc" ? "desc" : "asc";
    apply({ sort: sortKey, direction });
  }

  function onOpen(id: number) {
    const params = new URLSearchParams(searchParams);
    params.set("selected", String(id));
    setSearchParams(params);
  }

  const selectedId = searchParams.get("selected") ? Number(searchParams.get("selected")) : null;
  const total = items.data?.meta.total ?? 0;
  const rows = items.data?.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-xl font-semibold">Action items</h1>
        <p className="text-sm text-fg-muted">
          {total} item{total === 1 ? "" : "s"}
        </p>
      </div>

      <FilterBar filters={filters} onChange={apply}>
        <ColumnChooser columns={columns} visible={visible} onToggle={toggle} />
      </FilterBar>

      {items.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={ListChecks}
          title="No items match"
          description="Adjust the filters to see more."
        />
      ) : (
        <>
          <ItemsTable
            items={rows}
            usersById={byId}
            visible={visible}
            sort={filters.sort}
            direction={filters.direction}
            onSort={onSort}
            onOpen={onOpen}
            selectedId={selectedId}
          />
          <Pagination
            page={filters.page}
            limit={filters.limit}
            total={total}
            onPage={(page) => apply({ page })}
          />
        </>
      )}
    </div>
  );
}
