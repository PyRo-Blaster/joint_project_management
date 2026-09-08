import { ExportButton } from "@/features/items/ExportButton";

export function ExportPage() {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h2 className="text-base font-semibold">Export</h2>
      <p className="text-sm text-fg-muted">
        Download all current items as an Excel workbook in the original column layout (plus Last
        Updated and Updated By). To export a filtered subset, use the Export button on the Items
        table with filters applied.
      </p>
      <ExportButton />
    </div>
  );
}
