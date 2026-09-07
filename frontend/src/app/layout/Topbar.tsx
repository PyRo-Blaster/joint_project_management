import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

export function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold tracking-tight">Joint CMC Tracker</span>
        <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-fg-muted">GS098</span>
      </div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
