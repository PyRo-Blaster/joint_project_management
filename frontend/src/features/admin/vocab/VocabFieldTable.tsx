import { useState } from "react";
import { ArrowDown, ArrowUp, Check, Pencil, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import type { VocabTermOut } from "@/lib/api/types";

interface Props {
  terms: VocabTermOut[];
  onRename: (id: number, value: string) => void;
  onSetActive: (id: number, active: boolean) => void;
  onSwap: (a: VocabTermOut, b: VocabTermOut) => void;
}

export function VocabFieldTable({ terms, onRename, onSetActive, onSwap }: Props) {
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  return (
    <ul className="flex flex-col divide-y divide-border rounded-lg border border-border bg-surface">
      {terms.map((t, idx) => (
        <li key={t.id} className="flex items-center gap-3 px-3 py-2">
          <span className="flex flex-col">
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              disabled={idx === 0}
              aria-label="Move up"
              onClick={() => onSwap(t, terms[idx - 1])}
            >
              <ArrowUp className="size-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5"
              disabled={idx === terms.length - 1}
              aria-label="Move down"
              onClick={() => onSwap(t, terms[idx + 1])}
            >
              <ArrowDown className="size-3.5" />
            </Button>
          </span>

          {editing === t.id ? (
            <>
              <Input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="h-8 w-56"
                aria-label={`Rename ${t.value}`}
              />
              <Button
                size="icon"
                className="h-8 w-8"
                aria-label="Save"
                onClick={() => {
                  if (draft.trim()) onRename(t.id, draft.trim());
                  setEditing(null);
                }}
              >
                <Check className="size-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                aria-label="Cancel"
                onClick={() => setEditing(null)}
              >
                <X className="size-4" />
              </Button>
            </>
          ) : (
            <>
              <span className="flex-1 text-sm">
                {t.value} {!t.is_active && <Badge variant="outline">Inactive</Badge>}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                aria-label={`Edit ${t.value}`}
                onClick={() => {
                  setDraft(t.value);
                  setEditing(t.id);
                }}
              >
                <Pencil className="size-4" />
              </Button>
              <label className="flex items-center gap-1.5 text-xs text-fg-muted">
                <Checkbox checked={t.is_active} onCheckedChange={(v) => onSetActive(t.id, !!v)} />
                Active
              </label>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
