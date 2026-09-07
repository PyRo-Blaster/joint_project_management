import { Badge } from "@/components/ui/badge";
import { KIND_LABELS } from "@/lib/labels";
import type { Kind } from "@/lib/constants";

export function KindBadge({ kind }: { kind: string }) {
  return (
    <Badge variant={kind === "note" ? "outline" : "neutral"}>
      {KIND_LABELS[kind as Kind] ?? kind}
    </Badge>
  );
}
