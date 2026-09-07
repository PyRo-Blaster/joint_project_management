import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  applyApiFieldErrors,
  toastApiError,
  useCreateUpdateMutation,
  useItemUpdatesQuery,
} from "@/lib/api/hooks";
import { formatDate, formatDateTime } from "@/lib/format";

const schema = z.object({
  body: z.string().min(1, "Update text is required"),
  occurred_on: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

export function UpdatesPanel({ itemId }: { itemId: number }) {
  const updates = useItemUpdatesQuery(itemId);
  const create = useCreateUpdateMutation(itemId);
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  return (
    <div className="space-y-5">
      <form
        className="space-y-3 rounded-lg border border-line bg-surface-muted/40 p-3"
        onSubmit={handleSubmit(async (values) => {
          try {
            await create.mutateAsync({
              body: values.body,
              occurred_on: values.occurred_on || null,
            });
            reset({ body: "", occurred_on: "" });
          } catch (error) {
            if (!applyApiFieldErrors(error, setError)) toastApiError(error, "Could not post update");
          }
        })}
      >
        <div>
          <Label htmlFor="body">Post an update</Label>
          <Textarea id="body" rows={3} placeholder="What changed?" {...register("body")} />
          <FieldError message={errors.body?.message} />
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-44">
            <Label htmlFor="occurred_on">Occurred on</Label>
            <Input id="occurred_on" type="date" {...register("occurred_on")} />
          </div>
          <Button type="submit" disabled={isSubmitting || create.isPending}>
            {create.isPending ? "Posting…" : "Post update"}
          </Button>
        </div>
      </form>

      {updates.isLoading ? (
        <p className="text-sm text-ink-muted">Loading updates…</p>
      ) : updates.isError ? (
        <p className="text-sm text-rose-600">Failed to load updates.</p>
      ) : updates.data?.length === 0 ? (
        <p className="text-sm text-ink-muted">No timeline updates yet.</p>
      ) : (
        <ul className="space-y-3">
          {(updates.data ?? []).map((u) => (
            <li key={u.id} className="rounded-lg border border-line bg-surface-raised p-3">
              <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                <span className="font-medium text-ink">{u.author_name}</span>
                <Badge tone={u.author_org}>{u.author_org}</Badge>
                <span>{formatDate(u.occurred_on)}</span>
                {u.edited_at ? <span>edited {formatDateTime(u.edited_at)}</span> : null}
              </div>
              <p className="whitespace-pre-wrap text-sm text-ink">{u.body}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
