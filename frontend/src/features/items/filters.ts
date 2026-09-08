import type { Kind, OwnerOrg, Priority, Status } from "@/lib/constants";

export interface ItemFilters {
  status: Status[];
  priority: Priority[];
  group: string[];
  category: string[];
  owner_org: OwnerOrg[];
  kind: Kind | null;
  assignee_id: number | null;
  due_before: string | null;
  due_after: string | null;
  q: string | null;
  sort: string;
  direction: "asc" | "desc";
  page: number;
  limit: number;
}

export const DEFAULT_FILTERS: ItemFilters = {
  status: [],
  priority: [],
  group: [],
  category: [],
  owner_org: [],
  kind: null,
  assignee_id: null,
  due_before: null,
  due_after: null,
  q: null,
  sort: "entry_no",
  direction: "asc",
  page: 1,
  limit: 50,
};

const ARRAY_KEYS = ["status", "priority", "group", "category", "owner_org"] as const;

/** Read filters out of URL search params, falling back to defaults. */
export function parseFilters(params: URLSearchParams): ItemFilters {
  return {
    ...DEFAULT_FILTERS,
    status: params.getAll("status") as Status[],
    priority: params.getAll("priority") as Priority[],
    group: params.getAll("group"),
    category: params.getAll("category"),
    owner_org: params.getAll("owner_org") as OwnerOrg[],
    kind: (params.get("kind") as Kind | null) || null,
    assignee_id: params.get("assignee_id") ? Number(params.get("assignee_id")) : null,
    due_before: params.get("due_before"),
    due_after: params.get("due_after"),
    q: params.get("q"),
    sort: params.get("sort") || DEFAULT_FILTERS.sort,
    direction: params.get("direction") === "desc" ? "desc" : "asc",
    page: params.get("page") ? Math.max(1, Number(params.get("page"))) : 1,
    limit: params.get("limit") ? Number(params.get("limit")) : DEFAULT_FILTERS.limit,
  };
}

/** Serialize filters to URL search params, omitting empties so links stay clean. */
export function filtersToSearchParams(filters: ItemFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of ARRAY_KEYS) {
    for (const value of filters[key]) params.append(key, value);
  }
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.assignee_id != null) params.set("assignee_id", String(filters.assignee_id));
  if (filters.due_before) params.set("due_before", filters.due_before);
  if (filters.due_after) params.set("due_after", filters.due_after);
  if (filters.q) params.set("q", filters.q);
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set("sort", filters.sort);
  if (filters.direction !== DEFAULT_FILTERS.direction) params.set("direction", filters.direction);
  if (filters.page !== 1) params.set("page", String(filters.page));
  if (filters.limit !== DEFAULT_FILTERS.limit) params.set("limit", String(filters.limit));
  return params;
}

/** Params object for the API client (arrays become repeated query keys). */
export function filtersToApiParams(filters: ItemFilters): Record<string, unknown> {
  return {
    status: filters.status,
    priority: filters.priority,
    group: filters.group,
    category: filters.category,
    owner_org: filters.owner_org,
    kind: filters.kind,
    assignee_id: filters.assignee_id,
    due_before: filters.due_before,
    due_after: filters.due_after,
    q: filters.q,
    sort: filters.sort,
    direction: filters.direction,
    page: filters.page,
    limit: filters.limit,
  };
}

/** Count of active *content* filters (ignores sort/paging) for the "clear" affordance. */
export function activeFilterCount(filters: ItemFilters): number {
  let n = 0;
  for (const key of ARRAY_KEYS) n += filters[key].length;
  if (filters.kind) n++;
  if (filters.assignee_id != null) n++;
  if (filters.due_before) n++;
  if (filters.due_after) n++;
  if (filters.q) n++;
  return n;
}
