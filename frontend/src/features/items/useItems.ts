import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiList } from "@/lib/api/client";
import type { ItemOut, Meta } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { filtersToApiParams, type ItemFilters } from "./filters";

export function useItems(filters: ItemFilters) {
  return useQuery<{ data: ItemOut[]; meta: Meta }>({
    queryKey: qk.items.list(filters),
    queryFn: () => apiList<ItemOut>("/items", { params: filtersToApiParams(filters) as never }),
    placeholderData: keepPreviousData,
  });
}
