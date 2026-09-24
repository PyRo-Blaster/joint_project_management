import { Bot } from "lucide-react";
import { Badge } from "@/components/ui/badge";

/** Marks an audit row that arrived over MCP, naming the token that authorised it. */
export function AgentSource({
  via,
  tokenName,
}: {
  via?: string | null;
  tokenName?: string | null;
}) {
  if (via !== "mcp") return null;
  return (
    <Badge variant="outline" className="gap-1" title="Made by an agent through an API token">
      <Bot className="size-3" aria-hidden />
      via agent{tokenName ? ` · ${tokenName}` : ""}
    </Badge>
  );
}

/** An item an agent filed or changed that no person has confirmed yet. */
export function UnreviewedBadge() {
  return (
    <Badge
      variant="accent"
      className="gap-1"
      title="An agent filed or changed this; not yet confirmed"
    >
      <Bot className="size-3" aria-hidden />
      Unreviewed
    </Badge>
  );
}
