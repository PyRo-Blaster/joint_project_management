import type { ItemOut } from "@/lib/api/types";
import { groupIntoColumns, orderCards } from "./board-columns";

function item(o: Partial<ItemOut>): ItemOut {
  return {
    id: 0,
    program_id: 1,
    entry_no: 0,
    kind: "action",
    title: "t",
    details: "",
    group: "G",
    category: null,
    owner_org: "gensci",
    assignee_id: null,
    status: "open",
    priority: null,
    raised_on: "2026-01-01",
    source: null,
    due_on: null,
    completed_on: null,
    notes_risks: "",
    file_path: "",
    created_by: 1,
    created_at: "2026-01-01T00:00:00",
    updated_by: 1,
    updated_at: "2026-01-01T00:00:00",
    deleted_at: null,
    last_update_on: null,
    ...o,
  };
}

test("groups by status and skips unknown/absent statuses", () => {
  const cols = groupIntoColumns([
    item({ id: 1, status: "open" }),
    item({ id: 2, status: "blocked" }),
    item({ id: 3, status: null }),
  ]);
  expect(cols.open.map((i) => i.id)).toEqual([1]);
  expect(cols.blocked.map((i) => i.id)).toEqual([2]);
  expect(cols.on_hold).toEqual([]);
});

test("orders by priority then due date", () => {
  const ordered = orderCards([
    item({ id: 1, priority: null, due_on: null }),
    item({ id: 2, priority: "p1", due_on: "2026-03-01" }),
    item({ id: 3, priority: "p1", due_on: "2026-02-01" }),
    item({ id: 4, priority: "p2", due_on: null }),
  ]);
  expect(ordered.map((i) => i.id)).toEqual([3, 2, 4, 1]);
});
