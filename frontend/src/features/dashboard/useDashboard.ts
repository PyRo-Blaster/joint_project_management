import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { DashboardSummary } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useDashboard() {
  return useQuery({
    queryKey: qk.dashboard.summary(),
    queryFn: () => apiFetch<DashboardSummary>("/dashboard/summary"),
    staleTime: 30_000,
  });
}
