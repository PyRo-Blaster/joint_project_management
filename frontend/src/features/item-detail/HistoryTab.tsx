import { History } from "lucide-react";
import { DiffTable } from "@/components/domain/DiffTable";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsers } from "@/features/items/useUsers";
import { useItemHistory } from "./useHistory";

export function HistoryTab({ itemId }: { itemId: number }) {
  const history = useItemHistory(itemId);
  const { byId } = useUsers();
  const events = history.data ?? [];

  if (history.isLoading) return <Skeleton className="h-24 w-full" />;
  if (events.length === 0)
    return (
      <EmptyState icon={History} title="No history yet" description="Changes will appear here." />
    );

  return (
    <ol className="flex flex-col gap-4">
      {events.map((e) => {
        const changes = (e.changes ?? {}) as Record<string, { old?: unknown; new?: unknown }>;
        return (
          <li key={e.id} className="relative border-l border-border pl-4">
            <span className="absolute -left-1 top-1.5 size-2 rounded-full bg-accent" aria-hidden />
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{e.actor_name}</span>
              <span className="text-fg-muted">{e.summary}</span>
              <span className="text-fg-subtle">·</span>
              <RelativeTime iso={e.occurred_at} />
            </div>
            {Object.keys(changes).length > 0 && <DiffTable changes={changes} usersById={byId} />}
          </li>
        );
      })}
    </ol>
  );
}
