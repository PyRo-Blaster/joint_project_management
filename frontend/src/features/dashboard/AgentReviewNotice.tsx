import { Bot } from "lucide-react";
import { Link } from "react-router-dom";

/** Appears only when something from an agent is waiting; a standing zero is noise. */
export function AgentReviewNotice({ count }: { count: number }) {
  if (count <= 0) return null;
  return (
    <Link
      to="/items?needs_agent_review=true"
      className="flex items-center justify-between gap-3 rounded-lg border border-border bg-accent-weak px-4 py-3 text-sm hover:border-border-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex items-center gap-2 text-fg">
        <Bot className="size-4 text-accent" aria-hidden />
        <span>
          <span className="font-semibold tabular-nums">{count}</span>{" "}
          {count === 1 ? "item has" : "items have"} agent changes awaiting your eye.
        </span>
      </span>
      <span className="font-medium text-accent">Review</span>
    </Link>
  );
}
