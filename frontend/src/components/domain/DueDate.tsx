import { AlertTriangle } from "lucide-react";
import { daysUntil, formatDate, isOverdue } from "@/lib/format";
import { cn } from "@/lib/cn";

/** Due date with an overdue color + icon and a "due soon" amber when within `soonDays`. */
export function DueDate({ dueOn, soonDays = 14 }: { dueOn: string | null; soonDays?: number }) {
  if (!dueOn) return <span className="text-fg-subtle">—</span>;
  const overdue = isOverdue(dueOn);
  const remaining = daysUntil(dueOn);
  const soon = !overdue && remaining !== null && remaining <= soonDays;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-sm",
        overdue ? "font-medium text-danger" : soon ? "text-warning" : "text-fg-muted",
      )}
    >
      {overdue && <AlertTriangle className="size-3.5" aria-hidden />}
      {formatDate(dueOn)}
    </span>
  );
}
