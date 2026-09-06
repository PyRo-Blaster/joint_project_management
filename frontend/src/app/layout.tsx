import { NavLink, Outlet } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/auth-context";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/items", label: "Items", enabled: true },
  { to: "/dashboard", label: "Dashboard", enabled: false },
  { to: "/board", label: "Board", enabled: false },
  { to: "/admin", label: "Admin", enabled: false },
];

export function AppLayout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_#ecfeff_0,_transparent_42%),linear-gradient(#f8fafc,#f1f5f9)]">
      <header className="sticky top-0 z-30 border-b border-line/80 bg-surface-raised/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-accent">
                GS098
              </div>
              <div className="text-sm font-semibold tracking-tight">Joint CMC Tracker</div>
            </div>
            <nav className="hidden items-center gap-1 md:flex">
              {nav.map((item) =>
                item.enabled ? (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "rounded-md px-3 py-1.5 text-sm font-medium transition",
                        isActive
                          ? "bg-cyan-50 text-accent"
                          : "text-ink-muted hover:bg-surface-muted hover:text-ink",
                      )
                    }
                  >
                    {item.label}
                  </NavLink>
                ) : (
                  <span
                    key={item.to}
                    title="Coming in Phase 3"
                    className="cursor-not-allowed rounded-md px-3 py-1.5 text-sm text-ink-subtle"
                  >
                    {item.label}
                  </span>
                ),
              )}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right text-sm sm:block">
              <div className="font-medium">{user?.name}</div>
              <div className="text-xs text-ink-muted">
                {user?.email} · {user?.org} · {user?.role}
              </div>
            </div>
            <Button variant="secondary" size="sm" onClick={logout}>
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
