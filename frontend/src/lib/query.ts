import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Never retry auth/permission/validation failures; retry transient ones once.
        if (error instanceof ApiError && error.status < 500) return false;
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

/** Centralised query keys so invalidation is precise and typo-free. */
export const qk = {
  auth: { me: () => ["auth", "me"] as const },
  items: {
    all: () => ["items"] as const,
    list: (filters: unknown) => ["items", "list", filters] as const,
    detail: (id: number) => ["items", "detail", id] as const,
    updates: (id: number) => ["items", id, "updates"] as const,
    history: (id: number) => ["items", id, "history"] as const,
  },
  vocab: { list: () => ["vocab"] as const },
  users: { list: () => ["users"] as const, admin: () => ["users", "admin"] as const },
  invitations: { list: () => ["invitations"] as const },
  dashboard: { summary: () => ["dashboard", "summary"] as const },
  activity: { list: (filters: unknown) => ["activity", filters] as const },
};
