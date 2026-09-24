import { Bot } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ItemOut } from "@/lib/api/types";
import { useToast } from "@/lib/toast";
import { useAcknowledgeItem } from "@/features/items/useItemMutations";

/**
 * Shown while an agent's work on this item is unconfirmed. Opening the item does
 * not clear it: a glance is not a review. Editing the item, or "Looks right", does.
 */
export function AgentReviewBar({ item }: { item: ItemOut }) {
  const ack = useAcknowledgeItem(item.id);
  const { toast } = useToast();
  if (!item.needs_agent_review) return null;

  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-accent-weak px-6 py-3 text-sm"
    >
      <span className="flex items-center gap-2 text-fg">
        <Bot className="size-4 shrink-0 text-accent" aria-hidden />
        An agent filed or changed this item and no one has confirmed it yet. The History tab shows
        exactly what it did.
      </span>
      <Button
        size="sm"
        disabled={ack.isPending}
        onClick={async () => {
          try {
            await ack.mutateAsync();
            toast({ title: "Confirmed", description: "Marked as reviewed.", variant: "success" });
          } catch {
            toast({ title: "Could not confirm this item", variant: "error" });
          }
        }}
      >
        Looks right
      </Button>
    </div>
  );
}
