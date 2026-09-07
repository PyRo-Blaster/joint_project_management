import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MultiSelect, type Option } from "@/components/ui/multi-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { KINDS, OWNER_ORGS, PRIORITIES, STATUSES } from "@/lib/constants";
import { KIND_LABELS, OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "@/lib/labels";
import { activeFilterCount, type ItemFilters } from "./filters";
import { useUsers } from "./useUsers";
import { useVocab } from "./useVocab";

const STATUS_OPTIONS: Option[] = STATUSES.map((v) => ({ value: v, label: STATUS_LABELS[v] }));
const PRIORITY_OPTIONS: Option[] = PRIORITIES.map((v) => ({ value: v, label: PRIORITY_LABELS[v] }));
const OWNER_OPTIONS: Option[] = OWNER_ORGS.map((v) => ({ value: v, label: OWNER_LABELS[v] }));

export function FilterBar({
  filters,
  onChange,
  children,
}: {
  filters: ItemFilters;
  onChange: (next: Partial<ItemFilters>) => void;
  children?: React.ReactNode; // slot for column chooser + new-item button
}) {
  const { groups, categories } = useVocab();
  const { active: users } = useUsers();
  const [q, setQ] = useState(filters.q ?? "");

  useEffect(() => setQ(filters.q ?? ""), [filters.q]);
  useEffect(() => {
    const handle = setTimeout(() => {
      const next = q.trim() || null;
      if (next !== (filters.q ?? null)) onChange({ q: next });
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const count = activeFilterCount(filters);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search title & details…"
          className="w-64 pl-8"
          aria-label="Search items"
        />
      </div>

      <MultiSelect
        label="Status"
        options={STATUS_OPTIONS}
        selected={filters.status}
        onChange={(v) => onChange({ status: v as ItemFilters["status"] })}
      />
      <MultiSelect
        label="Priority"
        options={PRIORITY_OPTIONS}
        selected={filters.priority}
        onChange={(v) => onChange({ priority: v as ItemFilters["priority"] })}
      />
      <MultiSelect
        label="Owner"
        options={OWNER_OPTIONS}
        selected={filters.owner_org}
        onChange={(v) => onChange({ owner_org: v as ItemFilters["owner_org"] })}
      />
      <MultiSelect
        label="Group"
        options={groups.map((g) => ({ value: g.value, label: g.value }))}
        selected={filters.group}
        onChange={(v) => onChange({ group: v })}
      />
      <MultiSelect
        label="Category"
        options={categories.map((c) => ({ value: c.value, label: c.value }))}
        selected={filters.category}
        onChange={(v) => onChange({ category: v })}
      />

      <Select
        value={filters.kind ?? "all"}
        onValueChange={(v) => onChange({ kind: v === "all" ? null : (v as ItemFilters["kind"]) })}
      >
        <SelectTrigger className="h-8 w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All kinds</SelectItem>
          {KINDS.map((k) => (
            <SelectItem key={k} value={k}>
              {KIND_LABELS[k]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.assignee_id != null ? String(filters.assignee_id) : "all"}
        onValueChange={(v) => onChange({ assignee_id: v === "all" ? null : Number(v) })}
      >
        <SelectTrigger className="h-8 w-40">
          <SelectValue placeholder="Assignee" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Any assignee</SelectItem>
          {users.map((u) => (
            <SelectItem key={u.id} value={String(u.id)}>
              {u.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex items-center gap-1 text-sm text-fg-muted">
        <span>Due</span>
        <Input
          type="date"
          value={filters.due_after ?? ""}
          onChange={(e) => onChange({ due_after: e.target.value || null })}
          className="h-8 w-36"
          aria-label="Due after"
        />
        <span>–</span>
        <Input
          type="date"
          value={filters.due_before ?? ""}
          onChange={(e) => onChange({ due_before: e.target.value || null })}
          className="h-8 w-36"
          aria-label="Due before"
        />
      </div>

      {count > 0 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            onChange({
              status: [],
              priority: [],
              group: [],
              category: [],
              owner_org: [],
              kind: null,
              assignee_id: null,
              due_before: null,
              due_after: null,
              q: null,
            })
          }
        >
          <X className="size-4" /> Clear ({count})
        </Button>
      )}

      <div className="ml-auto flex items-center gap-2">{children}</div>
    </div>
  );
}
