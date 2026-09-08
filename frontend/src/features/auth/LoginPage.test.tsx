import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("shows validation errors before calling the API", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  renderPage();
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
});

test("surfaces an incorrect-credentials message on 401", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        success: false,
        data: null,
        error: { code: "unauthenticated", message: "no" },
        meta: null,
      }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    ),
  );
  renderPage();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "whatever");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  await waitFor(() => expect(screen.getByText(/incorrect email or password/i)).toBeInTheDocument());
});
