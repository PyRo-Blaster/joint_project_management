import { activeFilterCount, DEFAULT_FILTERS, filtersToSearchParams, parseFilters } from "./filters";

test("round-trips filters through URL params", () => {
  const filters = {
    ...DEFAULT_FILTERS,
    status: ["open", "blocked"] as const,
    owner_org: ["joint"] as const,
    q: "stability",
    direction: "desc" as const,
    page: 2,
  };
  const params = filtersToSearchParams(filters as never);
  const parsed = parseFilters(params);
  expect(parsed.status).toEqual(["open", "blocked"]);
  expect(parsed.owner_org).toEqual(["joint"]);
  expect(parsed.q).toBe("stability");
  expect(parsed.direction).toBe("desc");
  expect(parsed.page).toBe(2);
});

test("omits defaults from the query string", () => {
  const params = filtersToSearchParams(DEFAULT_FILTERS);
  expect(params.toString()).toBe("");
});

test("counts only content filters", () => {
  expect(activeFilterCount(DEFAULT_FILTERS)).toBe(0);
  expect(activeFilterCount({ ...DEFAULT_FILTERS, status: ["open"], q: "x", page: 3 })).toBe(2);
});
