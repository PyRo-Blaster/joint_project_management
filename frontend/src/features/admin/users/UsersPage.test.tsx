import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "@/lib/toast";
import { UsersPage } from "./UsersPage";

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = { success: true, data: [], error: null, meta: null };
    if (url.endsWith("/api/users")) {
      body = {
        success: true,
        data: [
          {
            id: 1,
            email: "ada@gensci.example",
            name: "Ada Admin",
            org: "gensci",
            role: "admin",
            is_active: true,
            last_login_at: "2026-02-01T00:00:00",
            created_at: "2026-01-01T00:00:00",
          },
        ],
        error: null,
        meta: null,
      };
    } else if (url.includes("/invitations")) {
      body = {
        success: true,
        data: [
          {
            id: 9,
            purpose: "invite",
            email: "mo@yarrow.example",
            org: "yarrow",
            role: "member",
            user_id: null,
            expires_at: "2030-01-01T00:00:00",
            accepted_at: null,
            created_by: 1,
            created_at: "2026-02-01T00:00:00",
          },
        ],
        error: null,
        meta: null,
      };
    }
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("lists users and pending invitations", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter>
          <UsersPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Ada Admin")).toBeInTheDocument();
  expect(await screen.findByText("mo@yarrow.example")).toBeInTheDocument();
});
