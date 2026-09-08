import { PRIORITY_LABELS } from "@/lib/labels";
import type { Priority } from "@/lib/constants";

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="text-fg-subtle">—</span>;
  const color = `var(--priority-${priority})`;
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold"
      style={{ color, backgroundColor: `color-mix(in oklch, ${color} 14%, transparent)` }}
    >
      {PRIORITY_LABELS[priority as Priority] ?? priority}
    </span>
  );
}
