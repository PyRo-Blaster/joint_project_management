import { useInfiniteQuery } from "@tanstack/react-query";
import { apiList } from "@/lib/api/client";
import type { AuditEventOut } from "@/lib/api/types";
import type { Org } from "@/lib/constants";
import { qk } from "@/lib/query";

const PAGE = 20;

/** Paginated global activity feed, optionally filtered by actor org. */
export function useActivity(org: Org | null) {
  return useInfiniteQuery({
    queryKey: qk.activity.list({ org }),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      apiList<AuditEventOut>("/activity", { params: { org, page: pageParam, limit: PAGE } }),
    getNextPageParam: (last, all) => {
      const loaded = all.reduce((n, p) => n + p.data.length, 0);
      return loaded < last.meta.total ? all.length + 1 : undefined;
    },
  });
}
