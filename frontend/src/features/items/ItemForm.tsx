import { Controller, useForm } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api/client";
import type { ItemCreate } from "@/lib/api/types";
import { KINDS, OWNER_ORGS, PRIORITIES, STATUSES } from "@/lib/constants";
import { KIND_LABELS, OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "@/lib/labels";
import { zodResolver } from "@/lib/form";
import { itemFormSchema, type ItemFormValues } from "./item-schema";
import { useUsers } from "./useUsers";
import { useVocab } from "./useVocab";

const NONE = "__none__";

function Field({
  label,
  error,
  children,
}: {
  label: string;
  error?: string;
  children: React.ReactNode;
}) {
  // Wrap the control in the label so it has an accessible name (getByLabel / e2e) and
  // clicking the label focuses the control.
  return (
    <Label className="flex flex-col gap-1.5 font-medium">
      <span>{label}</span>
      {children}
      {error && <span className="text-sm font-normal text-danger">{error}</span>}
    </Label>
  );
}

export function ItemForm({
  defaultValues,
  onSubmit,
  onCancel,
  submitLabel,
}: {
  defaultValues: ItemFormValues;
  onSubmit: (payload: ItemCreate) => Promise<void>;
  onCancel?: () => void;
  submitLabel: string;
}) {
  const { groups, categories } = useVocab();
  const { active: users } = useUsers();
  const {
    register,
    handleSubmit,
    control,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ItemFormValues>({ resolver: zodResolver(itemFormSchema), defaultValues });

  const kind = watch("kind");

  const submit = handleSubmit(async (values) => {
    const payload: ItemCreate = {
      kind: values.kind,
      title: values.title,
      details: values.details,
      group: values.group,
      category: values.category,
      owner_org: values.owner_org,
      assignee_id: values.assignee_id,
      status: values.kind === "note" ? null : values.status,
      priority: values.priority,
      raised_on: values.raised_on || null,
      source: values.source || null,
      due_on: values.due_on || null,
      notes_risks: values.notes_risks,
      file_path: values.file_path,
    };
    try {
      await onSubmit(payload);
    } catch (error) {
      if (error instanceof ApiError && error.fields) {
        for (const [field, message] of Object.entries(error.fields)) {
          setError(field as keyof ItemFormValues, { message });
        }
      } else {
        setError("root", { message: "Could not save. Try again." });
      }
    }
  });

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" noValidate>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Kind">
          <Controller
            control={control}
            name="kind"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KINDS.map((k) => (
                    <SelectItem key={k} value={k}>
                      {KIND_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
        <Field label="Owner">
          <Controller
            control={control}
            name="owner_org"
            render={({ field }) => (
              <Select value={field.value} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {OWNER_ORGS.map((o) => (
                    <SelectItem key={o} value={o}>
                      {OWNER_LABELS[o]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      </div>

      <Field label="Title" error={errors.title?.message}>
        <Input aria-invalid={!!errors.title} {...register("title")} />
      </Field>
      <Field label="Details" error={errors.details?.message}>
        <Textarea rows={3} {...register("details")} />
      </Field>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Group" error={errors.group?.message}>
          <Controller
            control={control}
            name="group"
            render={({ field }) => (
              <Select value={field.value || undefined} onValueChange={field.onChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a group" />
                </SelectTrigger>
                <SelectContent>
                  {groups.map((g) => (
                    <SelectItem key={g.id} value={g.value}>
                      {g.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
        <Field label="Category">
          <Controller
            control={control}
            name="category"
            render={({ field }) => (
              <Select
                value={field.value ?? NONE}
                onValueChange={(v) => field.onChange(v === NONE ? null : v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>None</SelectItem>
                  {categories.map((c) => (
                    <SelectItem key={c.id} value={c.value}>
                      {c.value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {kind === "action" && (
          <Field label="Status" error={errors.status?.message}>
            <Controller
              control={control}
              name="status"
              render={({ field }) => (
                <Select value={field.value ?? undefined} onValueChange={field.onChange}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a status" />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUSES.map((s) => (
                      <SelectItem key={s} value={s}>
                        {STATUS_LABELS[s]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </Field>
        )}
        <Field label="Priority">
          <Controller
            control={control}
            name="priority"
            render={({ field }) => (
              <Select
                value={field.value ?? NONE}
                onValueChange={(v) => field.onChange(v === NONE ? null : v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>None</SelectItem>
                  {PRIORITIES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {PRIORITY_LABELS[p]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Assignee">
          <Controller
            control={control}
            name="assignee_id"
            render={({ field }) => (
              <Select
                value={field.value != null ? String(field.value) : NONE}
                onValueChange={(v) => field.onChange(v === NONE ? null : Number(v))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Unassigned" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Unassigned</SelectItem>
                  {users.map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>
                      {u.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            )}
          />
        </Field>
        <Field label="Due date">
          <Controller
            control={control}
            name="due_on"
            render={({ field }) => (
              <Input
                type="date"
                value={field.value ?? ""}
                onChange={(e) => field.onChange(e.target.value || null)}
              />
            )}
          />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Field label="Raised on">
          <Controller
            control={control}
            name="raised_on"
            render={({ field }) => (
              <Input
                type="date"
                value={field.value ?? ""}
                onChange={(e) => field.onChange(e.target.value || null)}
              />
            )}
          />
        </Field>
        <Field label="Source">
          <Controller
            control={control}
            name="source"
            render={({ field }) => (
              <Input
                value={field.value ?? ""}
                onChange={(e) => field.onChange(e.target.value || null)}
              />
            )}
          />
        </Field>
      </div>

      <Field label="Notes / risks">
        <Textarea rows={2} {...register("notes_risks")} />
      </Field>
      <Field label="File path" error={errors.file_path?.message}>
        <Input placeholder="Pointer into the shared document tree" {...register("file_path")} />
      </Field>

      {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}

      <div className="flex justify-end gap-2 pt-2">
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
