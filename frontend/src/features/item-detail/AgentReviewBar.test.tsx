import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { AuditEventOut, ItemOut } from "@/lib/api/types";
import { ToastProvider } from "@/lib/toast";
import { AgentReviewBar } from "./AgentReviewBar";
import { pendingAgentWork } from "./agent-work";

const ITEM = {
  id: 7,
  entry_no: 7,
  title: "Agent-edited item",
  needs_agent_review: true,
  agent_ack_at: null,
} as unknown as ItemOut;

function event(overrides: Partial<AuditEventOut>): AuditEventOut {
  return {
    id: 1,
    program_id: 1,
    entity_type: "item",
    entity_id: 7,
    action: "updated",
    actor_id: 1,
    actor_name: "Ada Admin",
    actor_org: "gensci",
    occurred_at: "2026-09-24T10:00:00",
    changes: { due_on: { old: "2026-10-01", new: "2026-11-15" } },
    summary: "updated due_on on #7",
    via: "mcp",
    token_name: "Claude Code",
    reverted_by_event_id: null,
    can_undo: true,
    ...overrides,
  } as AuditEventOut;
}

function json(data: unknown) {
  return new Response(JSON.stringify({ success: true, data, error: null, meta: null }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function mockApi(history: AuditEventOut[]) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/history")) return json(history);
    if (url.includes("/revert")) return json(event({ id: 99, action: "reverted" }));
    return json({ ...ITEM, needs_agent_review: false });
  });
}

function renderBar(item: ItemOut) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <AgentReviewBar item={item} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("pending work is the agent's unrevoked field changes since the last confirmation", () => {
  const events = [
    event({ id: 1 }),
    event({ id: 2, via: "web" }),
    event({ id: 3, reverted_by_event_id: 9 }),
    event({ id: 4, action: "update_posted" }),
    event({ id: 5, occurred_at: "2026-09-01T00:00:00" }),
  ];
  expect(pendingAgentWork(events, "2026-09-10T00:00:00").map((e) => e.id)).toEqual([1]);
  expect(pendingAgentWork(events, null).map((e) => e.id)).toEqual([1, 5]);
});

test("renders nothing when no agent work is waiting", () => {
  mockApi([]);
  renderBar({ ...ITEM, needs_agent_review: false });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("lists each agent change with an undo, and confirms them all", async () => {
  const fetchSpy = mockApi([event({ id: 41 })]);
  renderBar(ITEM);
  expect(await screen.findByText(/due on 2026-10-01 → 2026-11-15/)).toBeInTheDocument();
  expect(screen.getByText(/via Claude Code/)).toBeInTheDocument();

  await userEvent.click(screen.getByRole("button", { name: /undo/i }));
  expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/api/activity/41/revert"))).toBe(
    true,
  );

  await userEvent.click(screen.getByRole("button", { name: /looks right/i }));
  expect(fetchSpy.mock.calls.some(([url]) => String(url).includes("/api/items/7/ack"))).toBe(true);
});
