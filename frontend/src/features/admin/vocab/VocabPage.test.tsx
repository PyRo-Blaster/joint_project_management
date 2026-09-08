import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VocabPage } from "./VocabPage";

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.includes("/vocab") && method === "POST") {
      return new Response(
        JSON.stringify({
          success: true,
          data: {
            id: 99,
            program_id: 1,
            field: "group",
            value: "New Group",
            sort_order: 3,
            is_active: true,
          },
          error: null,
          meta: null,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    }
    const body = {
      success: true,
      data: [
        {
          id: 1,
          program_id: 1,
          field: "group",
          value: "General Issues",
          sort_order: 0,
          is_active: true,
        },
        { id: 2, program_id: 1, field: "category", value: "QA", sort_order: 0, is_active: true },
      ],
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

test("lists terms per field and posts a new one", async () => {
  const fetchSpy = mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <VocabPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("General Issues")).toBeInTheDocument();
  expect(screen.getByText("QA")).toBeInTheDocument();

  const [groupAdd] = screen.getAllByPlaceholderText(/new term/i);
  await userEvent.type(groupAdd, "New Group");
  await userEvent.click(screen.getAllByRole("button", { name: /add/i })[0]);
  await waitFor(() =>
    expect(
      fetchSpy.mock.calls.some(
        ([u, i]) => String(u).includes("/vocab") && (i?.method ?? "GET") === "POST",
      ),
    ).toBe(true),
  );
});
