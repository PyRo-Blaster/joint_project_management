import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export interface FieldOption {
  value: string;
  label: string;
}

/** One <select> per raw value that could not be mapped, writing into the overrides map. */
export function UnmappedPicker({
  title,
  rawValues,
  options,
  mapping,
  onMap,
}: {
  title: string;
  rawValues: string[];
  options: FieldOption[];
  mapping: Record<string, string>;
  onMap: (raw: string, target: string) => void;
}) {
  if (rawValues.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium text-fg-muted">{title}</h3>
      <ul className="flex flex-col gap-2">
        {rawValues.map((raw) => (
          <li key={raw} className="flex items-center gap-3 text-sm">
            <code className="w-48 shrink-0 truncate rounded bg-surface-2 px-1.5 py-0.5">
              {raw || "(blank)"}
            </code>
            <span className="text-fg-subtle">→</span>
            <Select value={mapping[raw] ?? ""} onValueChange={(v) => onMap(raw, v)}>
              <SelectTrigger className="h-8 w-56">
                <SelectValue placeholder="Map to…" />
              </SelectTrigger>
              <SelectContent>
                {options.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </li>
        ))}
      </ul>
    </div>
  );
}
