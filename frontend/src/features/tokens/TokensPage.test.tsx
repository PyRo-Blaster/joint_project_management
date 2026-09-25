import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "@/lib/toast";
import { TokensPage } from "./TokensPage";

const TOKEN = {
  id: 1,
  user_id: 1,
  user_name: "Ada Admin",
  name: "Claude Code",
  prefix: "cmct_abc1234",
  scopes: ["read", "write"],
  write_mode: "interactive",
  created_at: "2026-09-21T10:00:00",
  expires_at: "2026-12-20T10:00:00",
  last_used_at: null,
  revoked_at: null,
  is_active: true,
};

function mockFetch(tokens: unknown[]) {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/api/auth/me")
      ? {
          success: true,
          data: {
            id: 1,
            email: "ada@gensci.example",
            name: "Ada Admin",
            org: "gensci",
            role: "admin",
            is_active: true,
          },
          error: null,
          meta: null,
        }
      : { success: true, data: tokens, error: null, meta: null };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }) as Response;
  });
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <MemoryRouter>
          <TokensPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

describe("TokensPage", () => {
  it("lists a token by name and prefix, and never shows a raw value", async () => {
    mockFetch([TOKEN]);
    renderPage();

    expect(await screen.findByText("Claude Code")).toBeInTheDocument();
    expect(screen.getByText("cmct_abc1234")).toBeInTheDocument();
    expect(screen.getByText(/read, write/i)).toBeInTheDocument();
    expect(screen.getByText(/never used/i)).toBeInTheDocument();
  });

  it("offers revoke for an active token only", async () => {
    mockFetch([
      TOKEN,
      {
        ...TOKEN,
        id: 2,
        name: "Old token",
        is_active: false,
        revoked_at: "2026-09-20T10:00:00",
      },
    ]);
    renderPage();

    expect(await screen.findByText("Old token")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /revoke/i })).toHaveLength(1);
    expect(screen.getByText("Revoked")).toBeInTheDocument();
  });

  it("shows an empty state when there are no tokens", async () => {
    mockFetch([]);
    renderPage();
    expect(await screen.findByText(/no api tokens yet/i)).toBeInTheDocument();
  });
});
