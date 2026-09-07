import { itemFormSchema, NEW_ITEM_DEFAULTS } from "./item-schema";

const valid = { ...NEW_ITEM_DEFAULTS, title: "Confirm EP", group: "General Issues" };

test("requires a title and a group", () => {
  expect(itemFormSchema.safeParse(NEW_ITEM_DEFAULTS).success).toBe(false);
  expect(itemFormSchema.safeParse(valid).success).toBe(true);
});

test("an action must have a status, a note must not need one", () => {
  expect(itemFormSchema.safeParse({ ...valid, status: null }).success).toBe(false);
  expect(itemFormSchema.safeParse({ ...valid, kind: "note", status: null }).success).toBe(true);
});
