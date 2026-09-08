import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OWNER_LABELS } from "@/lib/labels";
import type { OwnerOrg } from "@/lib/constants";

function Bars({
  data,
  labelOf,
}: {
  data: Record<string, number>;
  labelOf?: (k: string) => string;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  if (entries.length === 0) return <p className="text-sm text-fg-subtle">No open items.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {entries.map(([key, n]) => (
        <li key={key} className="flex items-center gap-3 text-sm">
          <span className="w-40 shrink-0 truncate text-fg-muted">
            {labelOf ? labelOf(key) : key}
          </span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
            <span
              className="block h-full rounded-full bg-accent"
              style={{ width: `${(n / max) * 100}%` }}
            />
          </span>
          <span className="w-8 shrink-0 text-right tabular-nums">{n}</span>
        </li>
      ))}
    </ul>
  );
}

export function Breakdowns({
  byGroup,
  byOwnerOrg,
}: {
  byGroup: Record<string, number>;
  byOwnerOrg: Record<string, number>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Open items by breakdown</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div>
          <h3 className="mb-2 text-sm font-medium text-fg-muted">By group</h3>
          <Bars data={byGroup} />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-fg-muted">By owner</h3>
          <Bars data={byOwnerOrg} labelOf={(k) => OWNER_LABELS[k as OwnerOrg] ?? k} />
        </div>
      </CardContent>
    </Card>
  );
}
