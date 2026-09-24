import { Bot } from "lucide-react";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { UndoButton } from "@/components/domain/UndoButton";
import { Button } from "@/components/ui/button";
import type { AuditEventOut, ItemOut } from "@/lib/api/types";
import { useToast } from "@/lib/toast";
import { useAcknowledgeItem } from "@/features/items/useItemMutations";
import { useItemHistory } from "./useHistory";

const REVIEWABLE = new Set(["created", "updated", "status_changed"]);

function show(value: unknown): string {
  return value === null || value === undefined || value === "" ? "(none)" : String(value);
}

/** The agent's work on this item since a person last confirmed it, newest first. */
export function pendingAgentWork(events: AuditEventOut[], ackAt: string | null): AuditEventOut[] {
  return events.filter(
    (e) =>
      e.via === "mcp" &&
      REVIEWABLE.has(e.action) &&
      !e.reverted_by_event_id &&
      (ackAt === null || e.occurred_at > ackAt),
  );
}

function describe(event: AuditEventOut): string {
  if (event.action === "created") return "Filed this item";
  const changes = Object.entries(event.changes ?? {}).filter(([field]) => field !== "completed_on");
  return changes
    .map(([field, change]) => {
      const c = change as { old?: unknown; new?: unknown };
      return `${field.replace(/_/g, " ")} ${show(c.old)} → ${show(c.new)}`;
    })
    .join("; ");
}

/**
 * Shown while an agent's work on this item is unconfirmed. Each change can be undone
 * here; "Looks right" confirms them all. Opening the item does not: a glance is not
 * a review.
 */
export function AgentReviewBar({ item }: { item: ItemOut }) {
  const ack = useAcknowledgeItem(item.id);
  const history = useItemHistory(item.id);
  const { toast } = useToast();
  if (!item.needs_agent_review) return null;
  const work = pendingAgentWork(history.data ?? [], item.agent_ack_at ?? null);

  return (
    <div role="status" className="border-b border-border bg-accent-weak px-6 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="flex items-center gap-2 font-medium text-fg">
          <Bot className="size-4 shrink-0 text-accent" aria-hidden />
          An agent changed this item and no one has confirmed it yet.
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
      {work.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {work.map((event) => (
            <li key={event.id} className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-fg-muted">
                {describe(event)} · <RelativeTime iso={event.occurred_at} />
                {event.token_name ? ` · via ${event.token_name}` : ""}
              </span>
              {event.can_undo && <UndoButton itemId={item.id} eventId={event.id} />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
