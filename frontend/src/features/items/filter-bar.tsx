import { useMemo } from "react";
import { Search, Columns3 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { ItemListParams, UserOut, VocabTermOut } from "@/lib/api/types";
import {
  KIND_LABELS,
  KINDS,
  OWNER_LABELS,
  OWNER_ORGS,
  PRIORITY_LABELS,
  PRIORITIES,
  STATUS_LABELS,
  STATUSES,
  ITEM_COLUMNS,
  type ItemColumnId,
} from "@/lib/constants";

function MultiSelect({
  label,
  values,
  options,
  onChange,
}: {
  label: string;
  values: string[];
  options: { value: string; label: string }[];
  onChange: (next: string[]) => void;
}) {
  return (
    <label className="flex min-w-[140px] flex-col gap-1 text-xs font-medium text-ink-muted">
      {label}
      <Select
        multiple
        value={values}
        className="h-24"
        onChange={(e) =>
          onChange(Array.from(e.target.selectedOptions).map((o) => o.value))
        }
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
    </label>
  );
}

export function FilterBar({
  filters,
  onChange,
  vocab,
  users,
  visibleColumns,
  onVisibleColumnsChange,
}: {
  filters: ItemListParams;
  onChange: (next: ItemListParams) => void;
  vocab: VocabTermOut[];
  users: UserOut[];
  visibleColumns: ItemColumnId[];
  onVisibleColumnsChange: (next: ItemColumnId[]) => void;
}) {
  const groups = useMemo(
    () => vocab.filter((v) => v.field === "group" && v.is_active).map((v) => v.value),
    [vocab],
  );
  const categories = useMemo(
    () => vocab.filter((v) => v.field === "category" && v.is_active).map((v) => v.value),
    [vocab],
  );

  return (
    <div className="space-y-3 rounded-xl border border-line bg-surface-raised p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <label className="relative min-w-[220px] flex-1">
          <span className="mb-1 block text-xs font-medium text-ink-muted">Search</span>
          <Search className="pointer-events-none absolute bottom-2.5 left-3 h-4 w-4 text-ink-subtle" />
          <Input
            className="pl-9"
            placeholder="Title, details, notes…"
            value={filters.q ?? ""}
            onChange={(e) => onChange({ ...filters, q: e.target.value || undefined, page: 1 })}
          />
        </label>
        <label className="w-36 text-xs font-medium text-ink-muted">
          Kind
          <Select
            className="mt-1"
            value={filters.kind ?? ""}
            onChange={(e) =>
              onChange({ ...filters, kind: e.target.value || undefined, page: 1 })
            }
          >
            <option value="">All</option>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {KIND_LABELS[k]}
              </option>
            ))}
          </Select>
        </label>
        <label className="w-44 text-xs font-medium text-ink-muted">
          Assignee
          <Select
            className="mt-1"
            value={filters.assignee_id?.toString() ?? ""}
            onChange={(e) =>
              onChange({
                ...filters,
                assignee_id: e.target.value ? Number(e.target.value) : undefined,
                page: 1,
              })
            }
          >
            <option value="">All</option>
            {users.map((u) => (
              <option key={u.id} value={u.id}>
                {u.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="w-36 text-xs font-medium text-ink-muted">
          Due after
          <Input
            className="mt-1"
            type="date"
            value={filters.due_after ?? ""}
            onChange={(e) =>
              onChange({ ...filters, due_after: e.target.value || undefined, page: 1 })
            }
          />
        </label>
        <label className="w-36 text-xs font-medium text-ink-muted">
          Due before
          <Input
            className="mt-1"
            type="date"
            value={filters.due_before ?? ""}
            onChange={(e) =>
              onChange({ ...filters, due_before: e.target.value || undefined, page: 1 })
            }
          />
        </label>
        <Button
          variant="secondary"
          onClick={() =>
            onChange({
              sort: "entry_no",
              direction: "asc",
              page: 1,
              limit: filters.limit ?? 50,
            })
          }
        >
          Clear filters
        </Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <MultiSelect
          label="Status"
          values={filters.status ?? []}
          options={STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))}
          onChange={(status) => onChange({ ...filters, status, page: 1 })}
        />
        <MultiSelect
          label="Priority"
          values={filters.priority ?? []}
          options={PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABELS[p] }))}
          onChange={(priority) => onChange({ ...filters, priority, page: 1 })}
        />
        <MultiSelect
          label="Owner"
          values={filters.owner_org ?? []}
          options={OWNER_ORGS.map((o) => ({ value: o, label: OWNER_LABELS[o] }))}
          onChange={(owner_org) => onChange({ ...filters, owner_org, page: 1 })}
        />
        <MultiSelect
          label="Group"
          values={filters.group ?? []}
          options={groups.map((g) => ({ value: g, label: g }))}
          onChange={(group) => onChange({ ...filters, group, page: 1 })}
        />
        <MultiSelect
          label="Category"
          values={filters.category ?? []}
          options={categories.map((c) => ({ value: c, label: c }))}
          onChange={(category) => onChange({ ...filters, category, page: 1 })}
        />
      </div>

      <details className="rounded-md border border-line bg-surface-muted/50 px-3 py-2">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-ink-muted">
          <Columns3 className="h-4 w-4" /> Column visibility
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
          {ITEM_COLUMNS.map((col) => {
            const checked = visibleColumns.includes(col.id);
            return (
              <label key={col.id} className="flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    const next = checked
                      ? visibleColumns.filter((id) => id !== col.id)
                      : [...visibleColumns, col.id];
                    onVisibleColumnsChange(next.length ? next : [col.id]);
                  }}
                />
                {col.label}
              </label>
            );
          })}
        </div>
      </details>
    </div>
  );
}
