import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ItemOut, Meta } from "@/lib/api/types";
import type { Status } from "@/lib/constants";
import { qk } from "@/lib/query";

type ListCache = { data: ItemOut[]; meta: Meta };

/** Move a card to a new status with an optimistic cache update and rollback on error. */
export function useMoveItemStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: Status }) =>
      apiFetch<ItemOut>(`/items/${id}`, { method: "PATCH", body: { status } }),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: qk.items.all() });
      const snapshot = qc.getQueriesData<ListCache>({ queryKey: ["items", "list"] });
      for (const [key, value] of snapshot) {
        if (!value) continue;
        qc.setQueryData<ListCache>(key, {
          ...value,
          data: value.data.map((it) => (it.id === id ? { ...it, status } : it)),
        });
      }
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.snapshot.forEach(([key, value]) => qc.setQueryData(key, value));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: qk.items.all() }),
  });
}
