import { AlertTriangle } from "lucide-react";
import type { ImportPreviewOut } from "@/lib/api/types";

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-md border border-border bg-surface px-3 py-1.5">
      <span className="text-fg-muted">{label}:</span>{" "}
      <span className="font-semibold tabular-nums">{value}</span>
    </span>
  );
}

export function PreviewTable({ preview }: { preview: ImportPreviewOut }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-4 text-sm">
        <Stat label="Rows" value={preview.total_rows} />
        <Stat label="Actions" value={preview.actions} />
        <Stat label="Notes" value={preview.notes} />
        <Stat label="Updates" value={preview.updates} />
      </div>

      {preview.errors.length > 0 && (
        <div className="rounded-md border border-danger/40 bg-danger/5 p-3 text-sm">
          <p className="mb-1 font-medium text-danger">Blocking errors</p>
          <ul className="list-inside list-disc text-fg-muted">
            {preview.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {preview.warnings.length > 0 && (
        <details className="rounded-md border border-warning/40 bg-warning/5 p-3 text-sm">
          <summary className="flex cursor-pointer items-center gap-2 font-medium text-warning">
            <AlertTriangle className="size-4" /> {preview.warnings.length} warnings
          </summary>
          <ul className="mt-2 list-inside list-disc text-fg-muted">
            {preview.warnings.map((w, i) => (
              <li key={i}>
                row {w.excel_row}
                {w.entry_no != null ? ` (entry ${w.entry_no})` : ""}: {w.message}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="max-h-72 overflow-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="border-b border-border text-left text-fg-muted">
              <th className="px-3 py-2 font-medium">Entry</th>
              <th className="px-3 py-2 font-medium">Title</th>
              <th className="px-3 py-2 font-medium">Group</th>
              <th className="px-3 py-2 font-medium">Owner</th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((r) => (
              <tr key={r.excel_row} className="border-b border-border/60 last:border-0">
                <td className="px-3 py-1.5 tabular-nums">{r.entry_no ?? "—"}</td>
                <td className="px-3 py-1.5">{r.title}</td>
                <td className="px-3 py-1.5">{r.group ?? "—"}</td>
                <td className="px-3 py-1.5">{r.owner_org ?? "—"}</td>
                <td className="px-3 py-1.5">{r.status ?? (r.kind === "note" ? "Note" : "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
