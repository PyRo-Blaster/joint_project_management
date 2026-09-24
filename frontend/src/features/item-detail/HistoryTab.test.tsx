import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HistoryTab } from "./HistoryTab";

function mockFetch(extra: Record<string, unknown> = {}) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/history")
      ? {
          success: true,
          data: [
            {
              id: 1,
              program_id: 1,
              entity_type: "item",
              entity_id: 3,
              action: "status_changed",
              actor_id: 5,
              actor_name: "Mo Member",
              actor_org: "yarrow",
              occurred_at: "2026-02-11T00:00:00",
              summary: "changed status Open → Blocked",
              changes: { status: { old: "open", new: "blocked" } },
              ...extra,
            },
          ],
          error: null,
          meta: null,
        }
      : { success: true, data: [], error: null, meta: null };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("renders an audit event with a field diff using human labels", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <HistoryTab itemId={3} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/changed status open → blocked/i)).toBeInTheDocument();
  expect(screen.getByText("Open")).toBeInTheDocument(); // old value, humanized
  expect(screen.getByText("Blocked")).toBeInTheDocument(); // new value, humanized
});

test("marks an agent's change with the token that made it", async () => {
  mockFetch({ via: "mcp", token_name: "Claude Code" });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <HistoryTab itemId={3} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/via agent · Claude Code/)).toBeInTheDocument();
});

test("does not mark a person's change", async () => {
  mockFetch({ via: "web", token_name: null });
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <HistoryTab itemId={3} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/changed status open → blocked/i)).toBeInTheDocument();
  expect(screen.queryByText(/via agent/)).not.toBeInTheDocument();
});
