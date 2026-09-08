import { statusLabel } from "@/lib/labels";

/** A status dot + label whose color comes from the --status-* token. */
export function StatusBadge({ status }: { status: string | null }) {
  const key = status ?? "note";
  const color = status ? `var(--status-${status})` : "var(--fg-subtle)";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-fg" data-status={key}>
      <span className="size-2 rounded-full" style={{ backgroundColor: color }} aria-hidden />
      {statusLabel(status)}
    </span>
  );
}
