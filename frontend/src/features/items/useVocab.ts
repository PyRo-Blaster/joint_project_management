import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { VocabTermOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

/** Active vocab terms, split into group/category (by sort_order). Inactive terms are hidden
 * from pickers (spec §8); the admin screen fetches the same cache but keeps inactive terms. */
export function useVocab() {
  const query = useQuery({
    queryKey: qk.vocab.list(),
    queryFn: () => apiFetch<VocabTermOut[]>("/vocab"),
    staleTime: 5 * 60_000,
  });
  const terms = query.data ?? [];
  const pick = (field: "group" | "category") =>
    terms
      .filter((t) => t.field === field && t.is_active)
      .sort((a, b) => a.sort_order - b.sort_order || a.value.localeCompare(b.value));
  return { ...query, groups: pick("group"), categories: pick("category") };
}
