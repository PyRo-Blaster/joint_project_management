import { useItemHistoryQuery } from "@/lib/api/hooks";
import { formatDateTime, relativeTime } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

function renderChangeValue(value: unknown): string {
  if (value === null || value === undefined) return "∅";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function HistoryPanel({ itemId }: { itemId: number }) {
  const history = useItemHistoryQuery(itemId);

  if (history.isLoading) return <p className="text-sm text-ink-muted">Loading history…</p>;
  if (history.isError) return <p className="text-sm text-rose-600">Failed to load history.</p>;
  if (!history.data?.length) return <p className="text-sm text-ink-muted">No audit events yet.</p>;

  return (
    <ul className="space-y-3">
      {history.data.map((event) => {
        const changes = event.changes ?? {};
        const entries = Object.entries(changes);
        return (
          <li key={event.id} className="rounded-lg border border-line bg-surface-raised p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
              <span className="font-medium text-ink">{event.actor_name}</span>
              <Badge tone={event.actor_org}>{event.actor_org}</Badge>
              <Badge>{event.action}</Badge>
              <span title={formatDateTime(event.occurred_at)}>{relativeTime(event.occurred_at)}</span>
            </div>
            <p className="mb-2 text-sm text-ink">{event.summary}</p>
            {entries.length ? (
              <dl className="space-y-1 rounded-md bg-surface-muted/60 p-2 font-mono text-xs">
                {entries.map(([field, change]) => {
                  const typed = change as { old?: unknown; new?: unknown } | unknown;
                  const isDiff =
                    typed &&
                    typeof typed === "object" &&
                    ("old" in (typed as object) || "new" in (typed as object));
                  return (
                    <div key={field} className="grid grid-cols-[7rem_1fr] gap-2">
                      <dt className="text-ink-muted">{field}</dt>
                      <dd className="text-ink">
                        {isDiff ? (
                          <>
                            <span className="text-rose-700">
                              {renderChangeValue((typed as { old?: unknown }).old)}
                            </span>
                            <span className="mx-1 text-ink-subtle">→</span>
                            <span className="text-emerald-700">
                              {renderChangeValue((typed as { new?: unknown }).new)}
                            </span>
                          </>
                        ) : (
                          renderChangeValue(typed)
                        )}
                      </dd>
                    </div>
                  );
                })}
              </dl>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
