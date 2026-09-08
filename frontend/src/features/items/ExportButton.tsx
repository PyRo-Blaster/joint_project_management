import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { downloadExport } from "@/lib/download";
import { filtersToSearchParams, type ItemFilters } from "./filters";

export function ExportButton({ filters }: { filters?: ItemFilters }) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() =>
        downloadExport(filters ? filtersToSearchParams(filters) : new URLSearchParams())
      }
    >
      <Download className="size-4" /> Export
    </Button>
  );
}
