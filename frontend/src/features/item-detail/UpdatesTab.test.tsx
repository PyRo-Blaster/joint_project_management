import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/lib/toast";
import { UpdatesTab } from "./UpdatesTab";

const json = (body: unknown) =>
  new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
const existingUpdate = () => ({
  id: 1,
  item_id: 9,
  author_id: 5,
  author_name: "Mo Member",
  author_org: "yarrow",
  body: "Stability data received",
  occurred_on: "2026-02-10",
  created_at: "2026-02-10T00:00:00",
  edited_at: null,
});
const newUpdate = () => ({ ...existingUpdate(), id: 2, body: "Sent to QA" });

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.includes("/auth/me")) {
      return json({
        success: true,
        data: {
          id: 5,
          name: "Mo Member",
          email: "m@y.co",
          org: "yarrow",
          role: "member",
          is_active: true,
          last_login_at: null,
          created_at: "2026-01-01T00:00:00",
        },
        error: null,
        meta: null,
      });
    }
    if (url.includes("/updates") && method === "POST") {
      return json({ success: true, data: newUpdate(), error: null, meta: null });
    }
    if (url.includes("/updates")) {
      return json({ success: true, data: [existingUpdate()], error: null, meta: null });
    }
    return json({ success: true, data: [], error: null, meta: null });
  });
}

function renderTab() {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <UpdatesTab itemId={9} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("lists existing updates and posts a new one", async () => {
  renderTab();
  expect(await screen.findByText("Stability data received")).toBeInTheDocument();

  await userEvent.type(screen.getByLabelText(/new update body/i), "Sent to QA");
  await userEvent.click(screen.getByRole("button", { name: /post update/i }));

  await waitFor(() =>
    expect(
      (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(
        ([u, i]) => String(u).includes("/updates") && (i?.method ?? "GET") === "POST",
      ),
    ).toBe(true),
  );
});
