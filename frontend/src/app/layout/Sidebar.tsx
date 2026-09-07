import { Columns3, LayoutDashboard, ListChecks, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/items", label: "Items", icon: ListChecks },
  { to: "/board", label: "Board", icon: Columns3 },
  { to: "/admin", label: "Admin", icon: Settings },
];

export function Sidebar() {
  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r border-border bg-surface p-3">
      {NAV.map(({ to, label, icon: Icon }) => (
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
