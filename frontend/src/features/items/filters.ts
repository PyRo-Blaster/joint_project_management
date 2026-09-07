import type { ItemListParams } from "@/lib/api/types";

const ARRAY_KEYS = ["status", "priority", "group", "category", "owner_org"] as const;
const SCALAR_KEYS = [
  "kind",
  "assignee_id",
  "due_before",
  "due_after",
  "q",
  "sort",
  "direction",
  "page",
  "limit",
] as const;

export function parseItemFilters(searchParams: URLSearchParams): ItemListParams {
  const params: ItemListParams = {
    sort: searchParams.get("sort") || "entry_no",
    direction: (searchParams.get("direction") as "asc" | "desc") || "asc",
    page: Number(searchParams.get("page") || 1),
    limit: Number(searchParams.get("limit") || 50),
  };

  for (const key of ARRAY_KEYS) {
    const values = searchParams.getAll(key).filter(Boolean);
    if (values.length) params[key] = values;
  }

  const kind = searchParams.get("kind");
  if (kind) params.kind = kind;
  const assignee = searchParams.get("assignee_id");
  if (assignee) params.assignee_id = Number(assignee);
  const dueBefore = searchParams.get("due_before");
  if (dueBefore) params.due_before = dueBefore;
  const dueAfter = searchParams.get("due_after");
  if (dueAfter) params.due_after = dueAfter;
  const q = searchParams.get("q");
  if (q) params.q = q;

  return params;
}

export function itemFiltersToSearchParams(
  filters: ItemListParams,
  extras?: Record<string, string | null | undefined>,
): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of ARRAY_KEYS) {
    for (const value of filters[key] ?? []) params.append(key, value);
  }
  for (const key of SCALAR_KEYS) {
    const value = filters[key];
    if (value === undefined || value === null || value === "") continue;
    if (key === "page" && Number(value) === 1) continue;
    if (key === "limit" && Number(value) === 50) continue;
    if (key === "sort" && value === "entry_no") continue;
    if (key === "direction" && value === "asc") continue;
    params.set(key, String(value));
  }
  if (extras) {
    for (const [k, v] of Object.entries(extras)) {
      if (v) params.set(k, v);
      else params.delete(k);
    }
  }
  return params;
}
