import { LayoutGrid, Table2 } from "lucide-react";
import { NavLink, useLocation, useSearchParams } from "react-router-dom";
import { cn } from "@/lib/cn";

const KEY = "cmc-items-view";

/** Persist the last chosen view so the sidebar returns the user where they left off. */
export function rememberView(view: "table" | "board") {
  try {
    localStorage.setItem(KEY, view);
  } catch {
    /* ignore */
  }
}

export function lastView(): "table" | "board" {
  try {
    return localStorage.getItem(KEY) === "board" ? "board" : "table";
  } catch {
    return "table";
  }
}

export function ViewToggle() {
  const [params] = useSearchParams();
  const location = useLocation();
  const qs = params.toString();
  const suffix = qs ? `?${qs}` : "";
  const link = (to: string, active: boolean, Icon: typeof Table2, label: string) => (
    <NavLink
      to={`${to}${suffix}`}
      onClick={() => rememberView(to === "/board" ? "board" : "table")}
      className={cn(
        "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium",
        active ? "bg-accent-weak text-accent" : "text-fg-muted hover:bg-surface-2",
      )}
    >
      <Icon className="size-4" />
      {label}
    </NavLink>
  );
  return (
    <div className="inline-flex rounded-md border border-border p-0.5">
      {link("/items", location.pathname.startsWith("/items"), Table2, "Table")}
      {link("/board", location.pathname.startsWith("/board"), LayoutGrid, "Board")}
    </div>
  );
}
