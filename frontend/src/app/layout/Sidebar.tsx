import { Columns3, LayoutDashboard, ListChecks, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";
import { useAuth } from "@/features/auth/useAuth";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, adminOnly: false },
  { to: "/items", label: "Items", icon: ListChecks, adminOnly: false },
  { to: "/board", label: "Board", icon: Columns3, adminOnly: false },
  { to: "/admin", label: "Admin", icon: Settings, adminOnly: true },
];

export function Sidebar() {
  const { user } = useAuth();
  const items = NAV.filter((n) => !n.adminOnly || user?.role === "admin");
  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r border-border bg-surface p-3">
      {items.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-accent-weak text-accent"
                : "text-fg-muted hover:bg-surface-2 hover:text-fg",
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
