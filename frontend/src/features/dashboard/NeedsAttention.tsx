import { Link } from "react-router-dom";
import { DueDate } from "@/components/domain/DueDate";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ItemBrief } from "@/lib/api/types";

function Group({ title, items, empty }: { title: string; items: ItemBrief[]; empty: string }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-fg-muted">
        {title} <span className="tabular-nums">({items.length})</span>
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-fg-subtle">{empty}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {items.map((i) => (
            <li key={i.id}>
              <Link
                to={`/items/${i.id}`}
                className="flex items-center justify-between gap-3 py-2 text-sm hover:text-accent"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="tabular-nums text-fg-subtle">#{i.entry_no}</span>
                  <span className="truncate">{i.title}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <PriorityBadge priority={i.priority} />
                  <DueDate dueOn={i.due_on} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NeedsAttention({
  needs,
}: {
  needs: { overdue: ItemBrief[]; due_soon: ItemBrief[]; stale: ItemBrief[] };
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Needs attention</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <Group title="Overdue" items={needs.overdue} empty="Nothing overdue." />
        <Group title="Due soon" items={needs.due_soon} empty="Nothing due soon." />
        <Group title="Stale (no update)" items={needs.stale} empty="No stale items." />
      </CardContent>
    </Card>
  );
}
