import { useState } from "react";
import { MessageSquare, Pencil, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import type { UpdateOut } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { useToast } from "@/lib/toast";
import { useAuth } from "@/features/auth/useAuth";
import { useCreateUpdate, useDeleteUpdate, useItemUpdates, usePatchUpdate } from "./useUpdates";

export function UpdatesTab({ itemId }: { itemId: number }) {
  const updates = useItemUpdates(itemId);
  const create = useCreateUpdate(itemId);
  const { toast } = useToast();
  const [body, setBody] = useState("");
  const [occurredOn, setOccurredOn] = useState("");

  async function post() {
    if (!body.trim()) return;
    await create.mutateAsync({ body: body.trim(), occurred_on: occurredOn || null });
    setBody("");
    setOccurredOn("");
    toast({ title: "Update posted", variant: "success" });
  }

  const rows = updates.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface-2/50 p-3">
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add an update…"
          rows={3}
          aria-label="New update body"
        />
        <div className="flex items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-sm text-fg-muted">
            Dated
            <Input
              type="date"
              value={occurredOn}
              onChange={(e) => setOccurredOn(e.target.value)}
              className="h-8 w-40"
              aria-label="Update date"
            />
          </label>
          <Button size="sm" onClick={post} disabled={!body.trim() || create.isPending}>
            Post update
          </Button>
        </div>
      </div>

      {updates.isLoading ? (
        <Skeleton className="h-20 w-full" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="No updates yet"
          description="Post the first update above."
        />
      ) : (
        <ol className="flex flex-col gap-3">
          {rows.map((u) => (
            <UpdateRow key={u.id} itemId={itemId} update={u} />
          ))}
        </ol>
      )}
    </div>
  );
}

function UpdateRow({ itemId, update }: { itemId: number; update: UpdateOut }) {
  const { user } = useAuth();
  const patch = usePatchUpdate(itemId);
  const del = useDeleteUpdate(itemId);
  const { toast } = useToast();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(update.body);

  const canEdit = user?.id === update.author_id || user?.role === "admin";

  return (
    <li className="rounded-lg border border-border bg-surface p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm">
          <span
            className="flex size-6 items-center justify-center rounded-full text-xs font-semibold"
            style={{
              backgroundColor: `color-mix(in oklch, var(--org-${update.author_org}) 20%, transparent)`,
              color: `var(--org-${update.author_org})`,
            }}
          >
            {update.author_name.slice(0, 2).toUpperCase()}
          </span>
          <span className="font-medium">{update.author_name}</span>
          <span className="text-fg-subtle">·</span>
          <time dateTime={update.occurred_on} className="text-fg-muted">
            {formatDate(update.occurred_on)}
          </time>
          {update.edited_at && <span className="text-xs text-fg-subtle">(edited)</span>}
        </div>
        {canEdit && !editing && (
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Edit update"
              onClick={() => {
                setDraft(update.body);
                setEditing(true);
              }}
            >
              <Pencil className="size-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Delete update"
              onClick={async () => {
                await del.mutateAsync(update.id);
                toast({ title: "Update deleted", variant: "success" });
              }}
            >
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        )}
      </div>
      {editing ? (
        <div className="mt-2 flex flex-col gap-2">
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
            aria-label="Edit update body"
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={!draft.trim() || patch.isPending}
              onClick={async () => {
                await patch.mutateAsync({ id: update.id, body: draft.trim() });
                setEditing(false);
                toast({ title: "Update saved", variant: "success" });
              }}
            >
              Save
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-2 whitespace-pre-wrap text-sm text-fg">{update.body}</p>
      )}
    </li>
  );
}
