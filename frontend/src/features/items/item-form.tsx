import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Button } from "@/components/ui/button";
import { FieldError } from "@/components/ui/field-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  applyApiFieldErrors,
  toastApiError,
  usePatchItemMutation,
} from "@/lib/api/hooks";
import type { ItemOut, VocabTermOut } from "@/lib/api/types";
import {
  OWNER_LABELS,
  OWNER_ORGS,
  PRIORITY_LABELS,
  PRIORITIES,
  STATUS_LABELS,
  STATUSES,
} from "@/lib/constants";

const schema = z.object({
  title: z.string().min(1).max(500),
  details: z.string(),
  group: z.string().min(1),
  category: z.string().nullable(),
  owner_org: z.enum(["gensci", "yarrow", "joint"]),
  status: z
    .enum(["open", "in_progress", "blocked", "on_hold", "completed", "cancelled"])
    .nullable(),
  priority: z.enum(["p1", "p2", "p3"]).nullable(),
  raised_on: z.string(),
  source: z.string().nullable(),
  due_on: z.string().nullable(),
  notes_risks: z.string(),
  file_path: z.string(),
});

type FormValues = z.infer<typeof schema>;

function emptyToNull(value: string | null | undefined) {
  if (value == null || value === "") return null;
  return value;
}

export function ItemForm({ item, vocab }: { item: ItemOut; vocab: VocabTermOut[] }) {
  const patch = usePatchItemMutation(item.id);
  const groups = vocab.filter((v) => v.field === "group" && v.is_active);
  const categories = vocab.filter((v) => v.field === "category" && v.is_active);
  const isNote = item.kind === "note";

  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      title: item.title,
      details: item.details ?? "",
      group: item.group,
      category: item.category,
      owner_org: item.owner_org as FormValues["owner_org"],
      status: (item.status as FormValues["status"]) ?? null,
      priority: (item.priority as FormValues["priority"]) ?? null,
      raised_on: item.raised_on?.slice(0, 10) ?? "",
      source: item.source,
      due_on: item.due_on?.slice(0, 10) ?? null,
      notes_risks: item.notes_risks ?? "",
      file_path: item.file_path ?? "",
    },
  });

  useEffect(() => {
    reset({
      title: item.title,
      details: item.details ?? "",
      group: item.group,
      category: item.category,
      owner_org: item.owner_org as FormValues["owner_org"],
      status: (item.status as FormValues["status"]) ?? null,
      priority: (item.priority as FormValues["priority"]) ?? null,
      raised_on: item.raised_on?.slice(0, 10) ?? "",
      source: item.source,
      due_on: item.due_on?.slice(0, 10) ?? null,
      notes_risks: item.notes_risks ?? "",
      file_path: item.file_path ?? "",
    });
  }, [item, reset]);

  return (
    <form
      className="space-y-4"
      onSubmit={handleSubmit(async (values) => {
        try {
          await patch.mutateAsync({
            title: values.title,
            details: values.details,
            group: values.group,
            category: emptyToNull(values.category),
            owner_org: values.owner_org,
            status: isNote ? null : values.status,
            priority: emptyToNull(values.priority) as FormValues["priority"],
            raised_on: values.raised_on || null,
            source: emptyToNull(values.source),
            due_on: emptyToNull(values.due_on),
            notes_risks: values.notes_risks,
            file_path: values.file_path,
          });
        } catch (error) {
          if (!applyApiFieldErrors(error, setError)) toastApiError(error, "Save failed");
        }
      })}
    >
      <div>
        <Label htmlFor="title">Title</Label>
        <Input id="title" {...register("title")} />
        <FieldError message={errors.title?.message} />
      </div>
      <div>
        <Label htmlFor="details">Details</Label>
        <Textarea id="details" rows={4} {...register("details")} />
        <FieldError message={errors.details?.message} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="group">Group</Label>
          <Select id="group" {...register("group")}>
            {groups.map((g) => (
              <option key={g.id} value={g.value}>
                {g.value}
              </option>
            ))}
          </Select>
          <FieldError message={errors.group?.message} />
        </div>
        <div>
          <Label htmlFor="category">Category</Label>
          <Select id="category" {...register("category")}>
            <option value="">—</option>
            {categories.map((c) => (
              <option key={c.id} value={c.value}>
                {c.value}
              </option>
            ))}
          </Select>
          <FieldError message={errors.category?.message} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="owner_org">Owner</Label>
          <Select id="owner_org" {...register("owner_org")}>
            {OWNER_ORGS.map((o) => (
              <option key={o} value={o}>
                {OWNER_LABELS[o]}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="priority">Priority</Label>
          <Select id="priority" {...register("priority")}>
            <option value="">—</option>
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {PRIORITY_LABELS[p]}
              </option>
            ))}
          </Select>
        </div>
      </div>
      {!isNote ? (
        <div>
          <Label htmlFor="status">Status</Label>
          <Select id="status" {...register("status")}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABELS[s]}
              </option>
            ))}
          </Select>
        </div>
      ) : null}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="raised_on">Raised on</Label>
          <Input id="raised_on" type="date" {...register("raised_on")} />
        </div>
        <div>
          <Label htmlFor="due_on">Due on</Label>
          <Input id="due_on" type="date" {...register("due_on")} />
        </div>
      </div>
      <div>
        <Label htmlFor="source">Source</Label>
        <Input id="source" {...register("source")} />
      </div>
      <div>
        <Label htmlFor="notes_risks">Notes / risks</Label>
        <Textarea id="notes_risks" rows={3} {...register("notes_risks")} />
      </div>
      <div>
        <Label htmlFor="file_path">File path</Label>
        <Input id="file_path" {...register("file_path")} />
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="submit" disabled={!isDirty || isSubmitting || patch.isPending}>
          {patch.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
