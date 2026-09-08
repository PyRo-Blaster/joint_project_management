import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ItemOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useItem(id: number | null) {
  return useQuery({
    queryKey: id != null ? qk.items.detail(id) : ["items", "detail", "none"],
    queryFn: () => apiFetch<ItemOut>(`/items/${id}`),
    enabled: id != null,
  });
}
