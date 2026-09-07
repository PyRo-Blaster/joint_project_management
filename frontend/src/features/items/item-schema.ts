import { z } from "zod";
import type { ItemOut } from "@/lib/api/types";
import {
  KINDS,
  OWNER_ORGS,
  PRIORITIES,
  STATUSES,
  type Kind,
  type OwnerOrg,
  type Priority,
  type Status,
} from "@/lib/constants";

const kindEnum = z.enum([...KINDS] as [Kind, ...Kind[]]);
const ownerEnum = z.enum([...OWNER_ORGS] as [OwnerOrg, ...OwnerOrg[]]);
const statusEnum = z.enum([...STATUSES] as [Status, ...Status[]]);
const priorityEnum = z.enum([...PRIORITIES] as [Priority, ...Priority[]]);

export const itemFormSchema = z
  .object({
    kind: kindEnum,
    title: z.string().min(1, "Title is required").max(500),
    details: z.string(),
    group: z.string().min(1, "Group is required"),
    category: z.string().nullable(),
    owner_org: ownerEnum,
    assignee_id: z.number().nullable(),
    status: statusEnum.nullable(),
    priority: priorityEnum.nullable(),
    raised_on: z.string().nullable(),
    source: z.string().nullable(),
    due_on: z.string().nullable(),
    notes_risks: z.string(),
    file_path: z.string().max(500),
  })
  .refine((v) => v.kind === "note" || v.status !== null, {
    path: ["status"],
    message: "Choose a status for an action item",
  });

export type ItemFormValues = z.infer<typeof itemFormSchema>;

export const NEW_ITEM_DEFAULTS: ItemFormValues = {
  kind: "action",
  title: "",
  details: "",
  group: "",
  category: null,
  owner_org: "gensci",
  assignee_id: null,
  status: "open",
  priority: null,
  raised_on: null,
  source: null,
  due_on: null,
  notes_risks: "",
  file_path: "",
};

/** Seed the shared form from a fetched item for editing. */
export function itemToFormValues(item: ItemOut): ItemFormValues {
  return {
    kind: item.kind as ItemFormValues["kind"],
    title: item.title,
    details: item.details,
    group: item.group,
    category: item.category,
    owner_org: item.owner_org as ItemFormValues["owner_org"],
    assignee_id: item.assignee_id,
    status: item.status as ItemFormValues["status"],
    priority: item.priority as ItemFormValues["priority"],
    raised_on: item.raised_on,
    source: item.source,
    due_on: item.due_on,
    notes_risks: item.notes_risks,
    file_path: item.file_path,
  };
}
