import { useState } from "react";
import { Sheet } from "@/components/ui/sheet";
import { useItemQuery, useVocabQuery } from "@/lib/api/hooks";
import { ItemForm } from "@/features/items/item-form";
import { UpdatesPanel } from "@/features/items/updates-panel";
import { HistoryPanel } from "@/features/items/history-panel";
import { StatusBadge, PriorityBadge, OwnerBadge } from "@/features/items/status-badge";
import { cn } from "@/lib/utils";

const tabs = [
  { id: "details", label: "Details" },
  { id: "updates", label: "Updates" },
  { id: "history", label: "History" },
] as const;

type TabId = (typeof tabs)[number]["id"];

export function ItemDetailSheet({
  itemId,
  open,
  onClose,
}: {
  itemId: number | null;
  open: boolean;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<TabId>("details");
  const itemQuery = useItemQuery(open ? itemId : null);
  const vocabQuery = useVocabQuery();
  const item = itemQuery.data;

  return (
    <Sheet
      open={open}
      onClose={onClose}
      wide
      title={
        item ? (
          <div className="flex min-w-0 flex-col gap-1">
            <div className="truncate">
              <span className="mr-2 font-mono text-sm text-ink-muted">#{item.entry_no}</span>
              {item.title}
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusBadge status={item.status} />
              <PriorityBadge priority={item.priority} />
              <OwnerBadge owner={item.owner_org} />
            </div>
          </div>
        ) : (
          "Item"
        )
      }
    >
      <div className="mb-4 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition",
              tab === t.id
                ? "border-accent text-accent"
                : "border-transparent text-ink-muted hover:text-ink",
            )}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {itemQuery.isLoading ? (
        <p className="text-sm text-ink-muted">Loading item…</p>
      ) : itemQuery.isError || !item ? (
        <p className="text-sm text-rose-600">Item could not be loaded.</p>
      ) : tab === "details" ? (
        <ItemForm item={item} vocab={vocabQuery.data ?? []} />
      ) : tab === "updates" ? (
        <UpdatesPanel itemId={item.id} />
      ) : (
        <HistoryPanel itemId={item.id} />
      )}
    </Sheet>
  );
}
