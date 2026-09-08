import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiUpload } from "@/lib/api/client";
import type { ImportCommitOut, ImportPreviewOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export interface Overrides {
  group: Record<string, string>;
  category: Record<string, string>;
  owner: Record<string, string>;
  status: Record<string, string>;
}

export const EMPTY_OVERRIDES: Overrides = { group: {}, category: {}, owner: {}, status: {} };

function form(file: File, overrides: Overrides): FormData {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("overrides", JSON.stringify(overrides));
  return fd;
}

export function usePreview() {
  return useMutation({
    mutationFn: ({ file, overrides }: { file: File; overrides: Overrides }) =>
      apiUpload<ImportPreviewOut>("/import/excel/preview", form(file, overrides)),
  });
}

export function useCommit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ file, overrides }: { file: File; overrides: Overrides }) =>
      apiUpload<ImportCommitOut>("/import/excel/commit", form(file, overrides)),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.items.all() });
      qc.invalidateQueries({ queryKey: qk.dashboard.summary() });
    },
  });
}
