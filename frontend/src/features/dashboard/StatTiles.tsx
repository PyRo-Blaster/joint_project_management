import { AlertTriangle, Clock, Flag, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";
import type { DashboardSummary } from "@/lib/api/types";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/cn";

function Tile({
  label,
  value,
  to,
  accent,
  icon: Icon,
}: {
  label: string;
  value: number;
  to?: string;
  accent?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const body = (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4 shadow-sm transition-colors hover:border-border-strong">
      <div className="flex items-center justify-between text-sm text-fg-muted">
        {label}
        {Icon && <Icon className="size-4" />}
      </div>
      <div
        className={cn("text-2xl font-semibold tabular-nums")}
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
    </div>
  );
  return to ? (
    <Link
      to={to}
      className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {body}
    </Link>
  ) : (
    body
  );
}

export function StatTiles({ summary }: { summary: DashboardSummary }) {
  const s = summary.open_by_status;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Tile label="Open" value={summary.open_total} to="/items" icon={ListChecks} />
      <Tile
        label={STATUS_LABELS.in_progress}
        value={s.in_progress ?? 0}
        to="/items?status=in_progress"
      />
      <Tile label={STATUS_LABELS.blocked} value={s.blocked ?? 0} to="/items?status=blocked" />
      <Tile label="P1" value={summary.open_p1} to="/items?priority=p1" icon={Flag} />
      <Tile
        label="Overdue"
        value={summary.overdue_count}
        accent="var(--danger)"
        icon={AlertTriangle}
      />
      <Tile label="Due soon" value={summary.due_soon_count} accent="var(--warning)" icon={Clock} />
    </div>
  );
}
