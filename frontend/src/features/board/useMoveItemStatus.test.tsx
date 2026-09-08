import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ItemOut } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { useMoveItemStatus } from "./useMoveItemStatus";

function item(id: number, status: string): ItemOut {
  return {
    id,
    program_id: 1,
    entry_no: id,
    kind: "action",
    title: "t",
    details: "",
    group: "G",
    category: null,
    owner_org: "gensci",
    assignee_id: null,
    status,
    priority: null,
    raised_on: "2026-01-01",
    source: null,
    due_on: null,
    completed_on: null,
    notes_risks: "",
    file_path: "",
    created_by: 1,
    created_at: "2026-01-01T00:00:00",
    updated_by: 1,
    updated_at: "2026-01-01T00:00:00",
    deleted_at: null,
    last_update_on: null,
  } as ItemOut;
}

function setup() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  qc.setQueryData(qk.items.list({ any: true }), {
    data: [item(1, "open")],
    meta: { total: 1, page: 1, limit: 50 },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  return { qc, wrapper };
}

const cachedStatus = (qc: QueryClient) =>
  qc.getQueryData<{ data: ItemOut[] }>(qk.items.list({ any: true }))!.data[0].status;

afterEach(() => vi.restoreAllMocks());

test("optimistically updates the cached card status", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ success: true, data: item(1, "blocked"), error: null, meta: null }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  const { qc, wrapper } = setup();
  const { result } = renderHook(() => useMoveItemStatus(), { wrapper });
  result.current.mutate({ id: 1, status: "blocked" });
  await waitFor(() => expect(cachedStatus(qc)).toBe("blocked"));
});

test("rolls back the cached status when the request fails", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        success: false,
        data: null,
        error: { code: "conflict", message: "no" },
        meta: null,
      }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    ),
  );
  const { qc, wrapper } = setup();
  const { result } = renderHook(() => useMoveItemStatus(), { wrapper });
  result.current.mutate({ id: 1, status: "blocked" });
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(cachedStatus(qc)).toBe("open");
});
