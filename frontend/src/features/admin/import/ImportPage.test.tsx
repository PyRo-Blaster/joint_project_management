import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/lib/toast";
import { ImportPage } from "./ImportPage";

function preview() {
  return {
    file_name: "sheet.xlsx",
    total_rows: 57,
    actions: 52,
    notes: 5,
    updates: 37,
    unmapped: { group: [], category: [], owner: ["formulation"], status: [] },
    errors: [],
    warnings: [{ excel_row: 3, entry_no: 2, message: "status blank, defaulted to open" }],
    committable: false,
    rows: [
      {
        excel_row: 2,
        entry_no: 1,
        kind: "action",
        title: "Confirm EP compliance",
        group: "General Issues",
        category: "QA",
        owner_org: "gensci",
        status: "open",
        priority: "p1",
        raised_on: "2026-02-05",
        due_on: null,
        updates: 0,
        warnings: [],
      },
    ],
  };
}

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = { success: true, data: [], error: null, meta: null };
    if (url.includes("/import/excel/preview"))
      body = { success: true, data: preview(), error: null, meta: null };
    else if (url.includes("/vocab")) body = { success: true, data: [], error: null, meta: null };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("previews an uploaded file and surfaces counts and unmapped values", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ImportPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
  const input = screen.getByLabelText(/spreadsheet file/i);
  await userEvent.upload(
    input,
    new File(["x"], "sheet.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }),
  );
  expect(await screen.findByText("57")).toBeInTheDocument();
  expect(await screen.findByText(/map unmapped values/i)).toBeInTheDocument();
  expect(screen.getByText("formulation")).toBeInTheDocument();
});
