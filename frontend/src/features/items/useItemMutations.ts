import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ItemCreate, ItemOut, ItemPatch } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useCreateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ItemCreate) => apiFetch<ItemOut>("/items", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.items.all() }),
  });
}

export function usePatchItem(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ItemPatch) => apiFetch<ItemOut>(`/items/${id}`, { method: "PATCH", body }),
    onSuccess: (item) => {
      qc.setQueryData(qk.items.detail(id), item);
      qc.invalidateQueries({ queryKey: qk.items.all() });
      qc.invalidateQueries({ queryKey: qk.items.history(id) });
    },
  });
}

export function useDeleteItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<ItemOut>(`/items/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.items.all() }),
  });
}

export function useRestoreItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<ItemOut>(`/items/${id}/restore`, { method: "POST" }),
    onSuccess: (item) => {
      qc.setQueryData(qk.items.detail(item.id), item);
      qc.invalidateQueries({ queryKey: qk.items.all() });
    },
  });
}
