import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ItemOut } from "@/lib/api/types";
import { DEFAULT_VISIBLE } from "./columns";
import { ItemsTable } from "./ItemsTable";

function makeItem(overrides: Partial<ItemOut>): ItemOut {
  return {
    id: 1,
    program_id: 1,
    entry_no: 1,
    kind: "action",
    title: "Confirm EP compliance",
    details: "",
    group: "General Issues",
    category: "QA",
    owner_org: "gensci",
    assignee_id: null,
    status: "open",
    priority: "p1",
    raised_on: "2026-02-05",
    source: null,
    due_on: "2026-03-01",
    completed_on: null,
    notes_risks: "",
    file_path: "",
    created_by: 1,
    created_at: "2026-02-05T00:00:00",
    updated_by: 1,
    updated_at: "2026-02-06T00:00:00",
    deleted_at: null,
    last_update_on: null,
    ...overrides,
  };
}

const noop = () => {};

test("renders rows, the note badge, and fires onOpen on click", async () => {
  const onOpen = vi.fn();
  render(
    <ItemsTable
      items={[
        makeItem({ id: 1 }),
        makeItem({ id: 2, entry_no: 2, kind: "note", status: null, title: "A decision" }),
      ]}
      usersById={new Map()}
      visible={new Set(DEFAULT_VISIBLE)}
      sort="entry_no"
      direction="asc"
      onSort={noop}
      onOpen={onOpen}
      selectedId={null}
    />,
  );
  expect(screen.getByText("Confirm EP compliance")).toBeInTheDocument();
  // A note renders "Note" in both the Kind badge and the Status column.
  expect(screen.getAllByText("Note").length).toBeGreaterThanOrEqual(1);
  await userEvent.click(screen.getByText("A decision"));
  expect(onOpen).toHaveBeenCalledWith(2);
});

test("clicking a sortable header requests that sort key", async () => {
  const onSort = vi.fn();
  render(
    <ItemsTable
      items={[makeItem({})]}
      usersById={new Map()}
      visible={new Set(DEFAULT_VISIBLE)}
      sort="entry_no"
      direction="asc"
      onSort={onSort}
      onOpen={noop}
      selectedId={null}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: /title/i }));
  expect(onSort).toHaveBeenCalledWith("title");
});
