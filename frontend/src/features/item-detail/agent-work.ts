import type { AuditEventOut } from "@/lib/api/types";

const REVIEWABLE = new Set(["created", "updated", "status_changed"]);

export function show(value: unknown): string {
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
