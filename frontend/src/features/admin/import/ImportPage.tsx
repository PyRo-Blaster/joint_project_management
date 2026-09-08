import { useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import type { ImportPreviewOut } from "@/lib/api/types";
import { OWNER_ORGS, STATUSES } from "@/lib/constants";
import { OWNER_LABELS, STATUS_LABELS } from "@/lib/labels";
import { useToast } from "@/lib/toast";
import { useVocab } from "@/features/items/useVocab";
import { PreviewTable } from "./PreviewTable";
import { UnmappedPicker, type FieldOption } from "./UnmappedPicker";
import { EMPTY_OVERRIDES, type Overrides, useCommit, usePreview } from "./useImport";

const OWNER_OPTS: FieldOption[] = OWNER_ORGS.map((v) => ({ value: v, label: OWNER_LABELS[v] }));
const STATUS_OPTS: FieldOption[] = STATUSES.map((v) => ({ value: v, label: STATUS_LABELS[v] }));

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [overrides, setOverrides] = useState<Overrides>(EMPTY_OVERRIDES);
  const [preview, setPreview] = useState<ImportPreviewOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const previewMut = usePreview();
  const commitMut = useCommit();
  const { toast } = useToast();
  const { groups, categories } = useVocab();

  const groupOpts: FieldOption[] = groups.map((g) => ({ value: g.value, label: g.value }));
  const categoryOpts: FieldOption[] = categories.map((c) => ({ value: c.value, label: c.value }));

  async function runPreview(nextFile: File, nextOverrides: Overrides) {
    setError(null);
    try {
      setPreview(await previewMut.mutateAsync({ file: nextFile, overrides: nextOverrides }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preview failed.");
    }
  }

  function onSelectFile(f: File | null) {
    setFile(f);
    setOverrides(EMPTY_OVERRIDES);
    setPreview(null);
    if (f) void runPreview(f, EMPTY_OVERRIDES);
  }

  function setMap(field: keyof Overrides, raw: string, target: string) {
    setOverrides((prev) => ({ ...prev, [field]: { ...prev[field], [raw]: target } }));
  }

  async function commit() {
    if (!file) return;
    setError(null);
    try {
      const result = await commitMut.mutateAsync({ file, overrides });
      toast({
        title: `Imported ${result.items_created} items, ${result.updates_created} updates`,
        variant: "success",
      });
      setFile(null);
      setPreview(null);
      setOverrides(EMPTY_OVERRIDES);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Import failed.");
    }
  }

  const unmapped = preview?.unmapped ?? {};
  const hasUnmapped =
    (unmapped.group?.length ?? 0) +
      (unmapped.category?.length ?? 0) +
      (unmapped.owner?.length ?? 0) +
      (unmapped.status?.length ?? 0) >
    0;

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <h2 className="text-base font-semibold">Import spreadsheet</h2>
        <p className="mt-1 text-sm text-fg-muted">
          Upload the master track sheet. Review the preview, map any unmapped values, then commit.
          Commit is all-or-nothing and rejects rows whose entry numbers already exist.
        </p>
      </div>

      <label className="flex w-fit cursor-pointer items-center gap-2 rounded-md border border-border-strong px-4 py-2 text-sm font-medium hover:bg-surface-2">
        <Upload className="size-4" />
        {file ? file.name : "Choose .xlsx file"}
        <input
          type="file"
          accept=".xlsx"
          className="sr-only"
          aria-label="Spreadsheet file"
          onChange={(e) => onSelectFile(e.target.files?.[0] ?? null)}
        />
      </label>

      {previewMut.isPending && <p className="text-sm text-fg-muted">Analysing…</p>}
      {error && <p className="text-sm text-danger">{error}</p>}

      {preview && (
        <>
          <PreviewTable preview={preview} />

          {hasUnmapped && (
            <div className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-4">
              <p className="text-sm font-medium">Map unmapped values</p>
              <UnmappedPicker
                title="Group"
                rawValues={unmapped.group ?? []}
                options={groupOpts}
                mapping={overrides.group}
                onMap={(r, t) => setMap("group", r, t)}
              />
              <UnmappedPicker
                title="Category"
                rawValues={unmapped.category ?? []}
                options={categoryOpts}
                mapping={overrides.category}
                onMap={(r, t) => setMap("category", r, t)}
              />
              <UnmappedPicker
                title="Owner"
                rawValues={unmapped.owner ?? []}
                options={OWNER_OPTS}
                mapping={overrides.owner}
                onMap={(r, t) => setMap("owner", r, t)}
              />
              <UnmappedPicker
                title="Status"
                rawValues={unmapped.status ?? []}
                options={STATUS_OPTS}
                mapping={overrides.status}
                onMap={(r, t) => setMap("status", r, t)}
              />
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                disabled={!file || previewMut.isPending}
                onClick={() => file && runPreview(file, overrides)}
              >
                Re-check with mappings
              </Button>
            </div>
          )}

          <Button disabled={!preview.committable || commitMut.isPending} onClick={commit}>
            {commitMut.isPending ? "Importing…" : "Commit import"}
          </Button>
          {!preview.committable && (
            <p className="text-sm text-fg-muted">
              Resolve the errors and unmapped values above, then re-check to enable commit.
            </p>
          )}
        </>
      )}
    </div>
  );
}
