import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useItemsQuery, useUsersQuery, useVocabQuery } from "@/lib/api/hooks";
import type { ItemColumnId } from "@/lib/constants";
import { FilterBar } from "@/features/items/filter-bar";
import { ItemsTable } from "@/features/items/items-table";
import { ItemDetailSheet } from "@/features/items/item-detail-sheet";
import {
  loadVisibleColumns,
  saveVisibleColumns,
} from "@/features/items/column-visibility";
import { itemFiltersToSearchParams, parseItemFilters } from "@/features/items/filters";

export function ItemsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const params = useParams();
  const navigate = useNavigate();
  const itemId = params.itemId ? Number(params.itemId) : null;
  const filters = useMemo(() => parseItemFilters(searchParams), [searchParams]);
  const itemsQuery = useItemsQuery(filters);
  const vocabQuery = useVocabQuery();
  const usersQuery = useUsersQuery(true);
  const [visibleColumns, setVisibleColumns] = useState<ItemColumnId[]>(() => loadVisibleColumns());

  useEffect(() => {
    saveVisibleColumns(visibleColumns);
  }, [visibleColumns]);

  const total = itemsQuery.data?.meta?.total ?? 0;
  const page = filters.page ?? 1;
  const limit = filters.limit ?? 50;
  const pageCount = Math.max(1, Math.ceil(total / limit));

  function updateFilters(next: typeof filters) {
    setSearchParams(itemFiltersToSearchParams(next), { replace: true });
  }

  function onSort(column: string) {
    if (filters.sort === column) {
      updateFilters({
        ...filters,
        direction: filters.direction === "asc" ? "desc" : "asc",
      });
    } else {
      updateFilters({ ...filters, sort: column, direction: "asc" });
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Action items</h1>
          <p className="text-sm text-ink-muted">
            {itemsQuery.isLoading ? "Loading…" : `${total} item${total === 1 ? "" : "s"}`}
            {" · filters sync to the URL for sharing"}
          </p>
        </div>
      </div>

      <FilterBar
        filters={filters}
        onChange={updateFilters}
        vocab={vocabQuery.data ?? []}
        users={usersQuery.data ?? []}
        visibleColumns={visibleColumns}
        onVisibleColumnsChange={setVisibleColumns}
      />

      {itemsQuery.isError ? (
        <p className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          Failed to load items.
        </p>
      ) : (
        <ItemsTable
          items={itemsQuery.data?.data ?? []}
          visibleColumns={visibleColumns}
          sort={filters.sort ?? "entry_no"}
          direction={filters.direction ?? "asc"}
          selectedId={itemId}
          onSort={onSort}
          onRowClick={(item) => {
            const qs = searchParams.toString();
            navigate(`/items/${item.id}${qs ? `?${qs}` : ""}`);
          }}
        />
      )}

      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">
          Page {page} of {pageCount}
        </p>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={page <= 1}
            onClick={() => updateFilters({ ...filters, page: page - 1 })}
          >
            Previous
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={page >= pageCount}
            onClick={() => updateFilters({ ...filters, page: page + 1 })}
          >
            Next
          </Button>
        </div>
      </div>

      <ItemDetailSheet
        itemId={itemId}
        open={itemId != null && !Number.isNaN(itemId)}
        onClose={() => {
          const qs = searchParams.toString();
          navigate(`/items${qs ? `?${qs}` : ""}`);
        }}
      />
    </div>
  );
}
