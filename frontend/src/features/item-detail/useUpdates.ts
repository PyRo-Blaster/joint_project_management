import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { UpdateOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useItemUpdates(itemId: number) {
  return useQuery({
    queryKey: qk.items.updates(itemId),
    queryFn: () => apiFetch<UpdateOut[]>(`/items/${itemId}/updates`),
  });
}

/** Invalidate the timeline, the item (updated_at/last_update_on change), the list, and history. */
function invalidateAround(qc: ReturnType<typeof useQueryClient>, itemId: number) {
  qc.invalidateQueries({ queryKey: qk.items.updates(itemId) });
  qc.invalidateQueries({ queryKey: qk.items.detail(itemId) });
  qc.invalidateQueries({ queryKey: qk.items.all() });
  qc.invalidateQueries({ queryKey: qk.items.history(itemId) });
}

export function useCreateUpdate(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; occurred_on: string | null }) =>
      apiFetch<UpdateOut>(`/items/${itemId}/updates`, { method: "POST", body }),
    onSuccess: () => invalidateAround(qc, itemId),
  });
}

export function usePatchUpdate(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: number; body?: string; occurred_on?: string | null }) =>
      apiFetch<UpdateOut>(`/items/${itemId}/updates/${id}`, { method: "PATCH", body: patch }),
    onSuccess: () => invalidateAround(qc, itemId),
  });
}

export function useDeleteUpdate(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<null>(`/items/${itemId}/updates/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateAround(qc, itemId),
  });
}
