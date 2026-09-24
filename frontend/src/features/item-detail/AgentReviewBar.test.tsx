import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ItemOut } from "@/lib/api/types";
import { ToastProvider } from "@/lib/toast";
import { AgentReviewBar } from "./AgentReviewBar";

const ITEM = {
  id: 7,
  entry_no: 7,
  title: "Agent-filed item",
  needs_agent_review: true,
  agent_ack_at: null,
} as unknown as ItemOut;

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

test("renders nothing when no agent work is waiting", () => {
  renderBar({ ...ITEM, needs_agent_review: false });
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});

test("asks a person to confirm, and posts the acknowledgement", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        success: true,
        data: { ...ITEM, needs_agent_review: false },
        error: null,
        meta: null,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );
  renderBar(ITEM);
  expect(screen.getByRole("status")).toHaveTextContent(/no one has confirmed it yet/);

  await userEvent.click(screen.getByRole("button", { name: /looks right/i }));

  const [url, init] = fetchSpy.mock.calls[0];
  expect(String(url)).toContain("/api/items/7/ack");
  expect((init as RequestInit).method).toBe("POST");
});
