import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/lib/toast";
import { ItemDetail } from "./ItemDetail";

function itemJson() {
  return {
    id: 7,
    program_id: 1,
    entry_no: 7,
    kind: "action",
    title: "Confirm EP compliance",
    details: "line two",
    group: "General Issues",
    category: "QA",
    owner_org: "gensci",
    assignee_id: null,
    status: "open",
    priority: "p1",
    raised_on: "2026-02-05",
    source: null,
    due_on: "2026-03-01",
    completed_on: null,
    notes_risks: "",
    file_path: "",
    created_by: 1,
    created_at: "2026-02-05T00:00:00",
    updated_by: 1,
    updated_at: "2026-02-06T00:00:00",
    deleted_at: null,
    last_update_on: null,
  };
}

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = { success: true, data: [], error: null, meta: null };
    if (url.includes("/items/7"))
      body = { success: true, data: itemJson(), error: null, meta: null };
    else if (url.includes("/auth/me"))
      body = {
        success: true,
        data: {
          id: 1,
          name: "A",
          email: "a@b.co",
          org: "gensci",
          role: "member",
          is_active: true,
          last_login_at: null,
          created_at: "2026-01-01T00:00:00",
        },
        error: null,
        meta: null,
      };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("loads and renders an item with the editable Details tab", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <TooltipProvider>
          <ItemDetail itemId={7} />
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(
    await screen.findByRole("heading", { name: /confirm ep compliance/i }),
  ).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: /save changes/i })).toBeInTheDocument();
});
