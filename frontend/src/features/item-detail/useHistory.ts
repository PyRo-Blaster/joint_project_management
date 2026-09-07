import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { AuditEventOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useItemHistory(itemId: number) {
  return useQuery({
    queryKey: qk.items.history(itemId),
    queryFn: () => apiFetch<AuditEventOut[]>(`/items/${itemId}/history`),
  });
}
