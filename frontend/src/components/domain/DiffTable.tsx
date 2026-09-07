import type { OwnerOrg, Priority, Status } from "@/lib/constants";
import type { UserBrief } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "@/lib/labels";

const FIELD_LABELS: Record<string, string> = {
  title: "Title",
  details: "Details",
  group: "Group",
  category: "Category",
  owner_org: "Owner",
  assignee_id: "Assignee",
  status: "Status",
  priority: "Priority",
  raised_on: "Raised on",
  source: "Source",
  due_on: "Due",
  completed_on: "Completed",
  notes_risks: "Notes / risks",
  file_path: "File path",
  kind: "Kind",
};

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function formatValue(field: string, value: unknown, usersById: Map<number, UserBrief>): string {
  if (value === null || value === undefined || value === "") return "—";
  if (field === "status") return STATUS_LABELS[value as Status] ?? String(value);
  if (field === "priority") return PRIORITY_LABELS[value as Priority] ?? String(value);
  if (field === "owner_org") return OWNER_LABELS[value as OwnerOrg] ?? String(value);
  if (field === "assignee_id") return usersById.get(Number(value))?.name ?? `#${value}`;
  if (field === "raised_on" || field === "due_on" || field === "completed_on")
    return formatDate(String(value));
  return String(value);
}

export function DiffTable({
  changes,
  usersById,
}: {
  changes: Record<string, { old?: unknown; new?: unknown }>;
  usersById: Map<number, UserBrief>;
}) {
  return (
    <table className="mt-2 w-full text-sm">
      <tbody>
        {Object.entries(changes).map(([field, diff]) => (
          <tr key={field} className="align-top">
            <td className="w-28 py-1 pr-3 text-fg-muted">{fieldLabel(field)}</td>
            <td className="py-1">
              <span className="text-fg-subtle line-through">
                {formatValue(field, diff.old, usersById)}
              </span>
              <span className="mx-1.5 text-fg-subtle">→</span>
              <span className="text-fg">{formatValue(field, diff.new, usersById)}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
