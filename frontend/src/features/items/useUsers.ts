import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { UserBrief } from "@/lib/api/types";
import { qk } from "@/lib/query";

/** The user directory keyed by id, for resolving and picking assignees. */
export function useUsers() {
  const query = useQuery({
    queryKey: qk.users.list(),
    queryFn: () => apiFetch<UserBrief[]>("/users/directory"),
    staleTime: 5 * 60_000,
  });
  const users = query.data ?? [];
  const byId = new Map(users.map((u) => [u.id, u]));
  return { ...query, users, byId, active: users.filter((u) => u.is_active) };
}
