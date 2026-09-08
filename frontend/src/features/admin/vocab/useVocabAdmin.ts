import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { VocabTermOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

type Field = "group" | "category";

export function useVocabAdmin() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: qk.vocab.list(),
    queryFn: () => apiFetch<VocabTermOut[]>("/vocab"),
  });
  const terms = query.data ?? [];
  const byField = (f: Field) =>
    terms
      .filter((t) => t.field === f)
      .sort((a, b) => a.sort_order - b.sort_order || a.value.localeCompare(b.value));
  const invalidate = () => qc.invalidateQueries({ queryKey: qk.vocab.list() });

  const create = useMutation({
    mutationFn: (body: { field: Field; value: string; sort_order: number }) =>
      apiFetch<VocabTermOut>("/vocab", { method: "POST", body }),
    onSuccess: invalidate,
  });
  const patch = useMutation({
    mutationFn: ({
      id,
      ...body
    }: {
      id: number;
      value?: string;
      sort_order?: number;
      is_active?: boolean;
    }) => apiFetch<VocabTermOut>(`/vocab/${id}`, { method: "PATCH", body }),
    onSuccess: invalidate,
  });

  return { ...query, groups: byField("group"), categories: byField("category"), create, patch };
}
