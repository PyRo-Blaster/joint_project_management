import { Badge } from "@/components/ui/badge";
import { KIND_LABELS, OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "@/lib/constants";

export function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <Badge tone="note">{KIND_LABELS.note}</Badge>;
  return <Badge tone={status}>{STATUS_LABELS[status as keyof typeof STATUS_LABELS] ?? status}</Badge>;
}

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="text-ink-subtle">—</span>;
  return (
    <Badge tone={priority}>{PRIORITY_LABELS[priority as keyof typeof PRIORITY_LABELS] ?? priority}</Badge>
  );
}

export function OwnerBadge({ owner }: { owner: string }) {
  return <Badge tone={owner}>{OWNER_LABELS[owner as keyof typeof OWNER_LABELS] ?? owner}</Badge>;
}
