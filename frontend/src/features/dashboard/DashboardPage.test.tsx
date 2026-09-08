import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";

function summary() {
  return {
    open_total: 12,
    open_by_status: { in_progress: 4, blocked: 2, open: 6 },
    open_p1: 3,
    overdue_count: 2,
    due_soon_count: 1,
    stale_count: 0,
    needs_attention: {
      overdue: [
        {
          id: 1,
          entry_no: 1,
          title: "Overdue item",
          status: "open",
          priority: "p1",
          owner_org: "gensci",
          due_on: "2026-01-01",
          last_update_on: null,
        },
      ],
      due_soon: [],
      stale: [],
    },
    by_group: { "General Issues": 6, "Gen1 (existing) CMC": 6 },
    by_owner_org: { gensci: 7, yarrow: 5 },
    recent_activity: [],
  };
}

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/dashboard/summary")
      ? { success: true, data: summary(), error: null, meta: null }
      : { success: true, data: [], error: null, meta: { total: 0, page: 1, limit: 20 } };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("renders stat tiles, needs-attention, and breakdowns from the summary", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Overdue item")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByText(/needs attention/i)).toBeInTheDocument();
  expect(screen.getByText("By group")).toBeInTheDocument();
});
