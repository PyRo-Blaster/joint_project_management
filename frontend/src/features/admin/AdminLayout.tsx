import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/cn";

const TABS = [
  { to: "/admin/users", label: "Users & invitations" },
  { to: "/admin/vocab", label: "Vocabularies" },
  { to: "/admin/import", label: "Import" },
  { to: "/admin/export", label: "Export" },
];

export function AdminLayout() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Admin</h1>
      <nav className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              cn(
                "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
                isActive
                  ? "border-accent text-fg"
                  : "border-transparent text-fg-muted hover:text-fg",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
