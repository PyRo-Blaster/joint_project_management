import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { ORG_LABELS } from "@/lib/labels";
import type { Org } from "@/lib/constants";
import { cn } from "@/lib/cn";
import { useActivity } from "./useActivity";

const ORG_TABS: { value: Org | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "gensci", label: "GenSci" },
  { value: "yarrow", label: "Yarrow" },
];

export function ActivityFeed() {
  const [org, setOrg] = useState<Org | null>(null);
  const query = useActivity(org);
  const events = query.data?.pages.flatMap((p) => p.data) ?? [];

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Recent activity</CardTitle>
        <div className="flex gap-1">
          {ORG_TABS.map((t) => (
            <button
              key={t.label}
              onClick={() => setOrg(t.value)}
              className={cn(
                "rounded px-2 py-1 text-xs font-medium",
                org === t.value ? "bg-accent-weak text-accent" : "text-fg-muted hover:bg-surface-2",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {query.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : events.length === 0 ? (
          <p className="text-sm text-fg-subtle">No activity yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {events.map((e) => (
              <li key={e.id} className="flex items-start gap-2 text-sm">
                <span
                  className="mt-1.5 size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: `var(--org-${e.actor_org})` }}
                  title={ORG_LABELS[e.actor_org] ?? e.actor_org}
                />
                <span className="min-w-0">
                  <span className="font-medium">{e.actor_name}</span>{" "}
                  <span className="text-fg-muted">{e.summary}</span>{" "}
                  <RelativeTime iso={e.occurred_at} />
                </span>
              </li>
            ))}
          </ul>
        )}
        {query.hasNextPage && (
          <Button
            variant="outline"
            size="sm"
            className="self-start"
            disabled={query.isFetchingNextPage}
            onClick={() => query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
