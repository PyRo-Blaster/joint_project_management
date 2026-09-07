import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { UserOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

/** The current user, or null when unauthenticated. 401 resolves to null (not an error state). */
export function useMe() {
  return useQuery({
    queryKey: qk.auth.me(),
    queryFn: async (): Promise<UserOut | null> => {
      try {
        return await apiFetch<UserOut>("/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useAuth() {
  const { data, isLoading, isFetched } = useMe();
  return { user: data ?? null, isLoading, isAuthenticated: !!data, isFetched };
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiFetch<UserOut>("/auth/login", { method: "POST", body }),
    onSuccess: (user) => qc.setQueryData(qk.auth.me(), user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<null>("/auth/logout", { method: "POST" }),
    onSuccess: () => {
      qc.setQueryData(qk.auth.me(), null);
      qc.clear();
    },
  });
}

export function useAcceptInvite() {
  return useMutation({
    mutationFn: (body: { token: string; name: string; password: string }) =>
      apiFetch<null>("/auth/accept-invite", { method: "POST", body }),
  });
}
