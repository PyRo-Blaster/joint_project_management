import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";

function renderAt(status: number) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify(
        status === 200
          ? {
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
            }
          : {
              success: false,
              data: null,
              error: { code: "unauthenticated", message: "no" },
              meta: null,
            },
      ),
      { status, headers: { "Content-Type": "application/json" } },
    ),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/items"]}>
        <Routes>
          <Route path="/login" element={<p>Login screen</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/items" element={<p>Secret items</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("renders the child when authenticated", async () => {
  renderAt(200);
  expect(await screen.findByText("Secret items")).toBeInTheDocument();
});

test("redirects to /login when unauthenticated", async () => {
  renderAt(401);
  await waitFor(() => expect(screen.getByText("Login screen")).toBeInTheDocument());
});
