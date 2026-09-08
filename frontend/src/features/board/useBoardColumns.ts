import { useItems } from "@/features/items/useItems";
import type { ItemFilters } from "@/features/items/filters";
import { groupIntoColumns } from "./board-columns";

/** Fetch all matching action items (no paging) and group them into columns. */
export function useBoardColumns(filters: ItemFilters) {
  const query = useItems({ ...filters, kind: "action", status: [], page: 1, limit: 200 });
  const items = query.data?.data ?? [];
  return { ...query, columns: groupIntoColumns(items), total: query.data?.meta.total ?? 0 };
}
