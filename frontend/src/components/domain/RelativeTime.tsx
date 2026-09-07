import { formatDate, relativeTime } from "@/lib/format";

export function RelativeTime({ iso }: { iso: string | null }) {
  if (!iso) return <span className="text-fg-subtle">—</span>;
  return (
    <time dateTime={iso} title={formatDate(iso)} className="text-fg-muted">
      {relativeTime(iso)}
    </time>
  );
}
