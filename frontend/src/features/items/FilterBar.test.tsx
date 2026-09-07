import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DEFAULT_FILTERS, type ItemFilters } from "./filters";
import { FilterBar } from "./FilterBar";

// NOTE: Radix overlays (Popover/Select) cannot be *opened* under jsdom — mounting the
// overlay deadlocks the event loop (a known Radix FocusScope/jsdom limitation). These tests
// therefore exercise wiring that does not require opening an overlay: the debounced search,
// the "clear" affordance, and the selected-count badge that reflects the `selected` prop.
// Overlay open/select interactions are verified against the real app.

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/vocab")
      ? {
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
          ],
          error: null,
          meta: null,
        }
      : url.includes("/users/directory")
        ? {
            success: true,
            data: [{ id: 5, name: "Mo Member", org: "yarrow", is_active: true }],
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

function renderBar(filters: ItemFilters = DEFAULT_FILTERS) {
  mockFetch();
  const onChange = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <FilterBar filters={filters} onChange={onChange} />
    </QueryClientProvider>,
  );
  return onChange;
}

afterEach(() => vi.restoreAllMocks());

test("typing in search debounces into onChange", async () => {
  const onChange = renderBar();
  await userEvent.type(screen.getByLabelText(/search items/i), "stability");
  await waitFor(() => expect(onChange).toHaveBeenCalledWith({ q: "stability" }));
});

test("shows a count badge for preselected filters and clears them", async () => {
  const onChange = renderBar({ ...DEFAULT_FILTERS, status: ["open", "blocked"] });
  // The Status trigger shows the active count without opening the overlay.
  const statusButton = screen.getByRole("button", { name: /^status/i });
  expect(statusButton).toHaveTextContent("2");
  // The clear affordance appears and resets every content filter.
  await userEvent.click(screen.getByRole("button", { name: /clear \(2\)/i }));
  expect(onChange).toHaveBeenCalledWith(
    expect.objectContaining({ status: [], q: null, assignee_id: null }),
  );
});
