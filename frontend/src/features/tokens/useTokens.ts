import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { TokenCreate, TokenCreated, TokenOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useTokens(all: boolean) {
  return useQuery({
    queryKey: qk.tokens.list(all),
    queryFn: () => apiFetch<TokenOut[]>("/tokens", { params: { all } }),
  });
}

export function useCreateToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TokenCreate) => apiFetch<TokenCreated>("/tokens", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.tokens.all() }),
  });
}

export function useRevokeToken() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<TokenOut>(`/tokens/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.tokens.all() }),
  });
}
