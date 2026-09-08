# Phase 3: Board, Dashboard, and Admin — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the app's remaining screens on top of the Phase 2 frontend core — a Kanban board with drag-to-change-status, a dashboard (stat tiles, needs-attention, activity feed, breakdowns), and the admin area (users & invitations, vocabularies, Excel import preview→commit, and export) — plus the frontend test coverage the spec names for these screens.

**Architecture:** New feature folders under `frontend/src/features/` (`dashboard`, `board`, `admin`) consuming the already-generated OpenAPI DTO types and the envelope-aware client, TanStack Query hooks, and the design-token primitives built in Phase 2. Server state flows through the same `apiFetch`/`apiList` + `qk` query-key factory. The board's status change is an **optimistic mutation** (cache update on mutate, rollback on error) tested as a hook; the drag gesture itself uses `@dnd-kit` and is validated by the Phase 4 Playwright e2e. The Table/Board toggle and board column collapse persist per-browser in `localStorage`, matching the existing column-visibility pattern.

**Tech Stack:** Everything from Phase 2 (React 19, TS, Vite 6, Tailwind v4, TanStack Query v5, react-router v7, react-hook-form + zod, Radix, lucide, Vitest + Testing Library) plus **`@dnd-kit/core` + `@dnd-kit/sortable`** for accessible drag-and-drop.

**Spec:** `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md` — §10 (screens, dashboard summary), §9 (import/export), §6 (permissions), §7 (API), §8 (vocab). **Prior plans:** Phase 1 backend (`…/plans/2026-09-06-phase1-backend-core.md`), Phase 2 frontend core (`…/plans/2026-09-06-phase2-frontend-core.md`). **Phase 2 dev log:** `…/logs/2026-09-06-phase2-dev-log.md` — read its "Radix overlays deadlock jsdom" and Python-3.14-rc notes before running any test.

**Scope (this plan = Phase 3 only).** In: dashboard, board + Table/Board toggle, admin (users/invitations, vocab, import, export UI), and Vitest coverage for these. Out (Phase 4): CI workflow, Playwright e2e, Postgres/proxy compose profiles, deployment note. The generated API client already exists (Phase 2, `src/lib/api/`); this plan only regenerates types if a backend DTO changes (none is expected).

---

## Conventions for every task

- Repository root is the git repo root. Frontend commands run from `frontend/`. Commits run from the repo root. **Develop on branch `claude/phase-2-frontend-plan-p8h3e5`** (the open PR #2 branch) unless the user directs otherwise; if that PR has already merged, restart the branch from the latest default branch per the repo's branch policy.
- **Commit trailer:** end every commit with the co-authorship trailer your session requires; never embed a model version string in a committed file. Example blocks below show the subject/body only.
- **Cadence:** failing test (RED) → confirm it fails → minimal code (GREEN) → run the stated command → commit. One commit per task unless noted.
- **Testing reality (from Phase 2, do not relearn the hard way):**
  - Backend tests must run on **Python 3.13** locally: `uv run --python 3.13.12 pytest` (the pinned 3.14 resolves to an rc that breaks pydantic). This plan is frontend-only, but any backend check uses that invocation.
  - **Opening a Radix or @dnd-kit overlay/gesture inside jsdom hangs the event loop.** Test *logic and rendered output*, not the open/drag gesture. The board's move is covered by testing the `useMoveItemStatus` hook directly; the gesture is a Phase 4 Playwright case. Overlays (Select/Popover/Dialog) render fine **closed** — only opening them hangs.
  - `test/setup.ts` already stubs `matchMedia`, pointer capture, `PointerEvent`, and `ResizeObserver`.
- **Types come from the backend** (`src/lib/api/types.ts` aliases over `schema.d.ts`). Never hand-retype a DTO. Labels come from `src/lib/labels.ts`.
- **Permissions (spec §6):** admin-only screens (users, invitations, vocab write, import) are gated in the router by an `AdminRoute` and never rely on hiding UI alone — the backend also enforces. Members reaching an admin route see a "not authorised" page.
- **Enum/label single source:** reuse `STATUS_LABELS`, `OWNER_LABELS`, `PRIORITY_LABELS`, `statusLabel`, and the domain badges from Phase 2.

## File structure (new/changed)

```
frontend/src/
├── app/
│   ├── router.tsx                      # replace ComingSoon stubs with real routes; add AdminRoute + admin children
│   ├── AdminRoute.tsx                  # gate: admin-only, else NotAuthorised
│   └── NotAuthorised.tsx
├── features/
│   ├── dashboard/
│   │   ├── useDashboard.ts  useActivity.ts
│   │   ├── DashboardPage.tsx  StatTiles.tsx  NeedsAttention.tsx  Breakdowns.tsx
│   │   └── ActivityFeed.tsx            # shared; also usable elsewhere
│   ├── board/
│   │   ├── BoardPage.tsx  BoardColumn.tsx  BoardCard.tsx
│   │   ├── useBoardColumns.ts          # group items by status, order by priority then due
│   │   ├── useMoveItemStatus.ts        # optimistic PATCH + rollback
│   │   ├── board-prefs.ts              # collapsed columns persisted to localStorage
│   │   └── ViewToggle.tsx              # Table/Board, persisted; used on the items page
│   └── admin/
│       ├── AdminLayout.tsx             # sub-nav: Users · Vocab · Import · Export
│       ├── users/ UsersPage.tsx  useUsersAdmin.ts  InviteDialog.tsx  ResetLinkDialog.tsx  UserRow.tsx
│       ├── vocab/  VocabPage.tsx  useVocabAdmin.ts  VocabFieldTable.tsx  AddTermRow.tsx
│       └── import/ ImportPage.tsx  useImport.ts  PreviewTable.tsx  UnmappedPicker.tsx
├── components/ui/  copy-button.tsx  (small) alert.tsx  table.tsx (shared <Table> shell)
└── lib/  download.ts                    # authenticated file download helper (export)
```

---

### Task 1: Dashboard — summary hooks, stat tiles, needs-attention, breakdowns, activity feed

**Files:**
- Create: `frontend/src/features/dashboard/useDashboard.ts`, `useActivity.ts`
- Create: `frontend/src/features/dashboard/StatTiles.tsx`, `NeedsAttention.tsx`, `Breakdowns.tsx`, `ActivityFeed.tsx`, `DashboardPage.tsx`
- Modify: `frontend/src/app/router.tsx` (route `/dashboard` → `DashboardPage`)
- Test: `frontend/src/features/dashboard/DashboardPage.test.tsx`

`DashboardSummary` shape (from `src/lib/api/types.ts`, generated): `open_total`, `open_by_status: Record<string,number>`, `open_p1`, `overdue_count`, `due_soon_count`, `stale_count`, `needs_attention: { overdue: ItemBrief[]; due_soon: ItemBrief[]; stale: ItemBrief[] }`, `by_group: Record<string,number>`, `by_owner_org: Record<string,number>`, `recent_activity: AuditEventOut[]`. `ItemBrief`: `{ id, entry_no, title, status, priority, owner_org, due_on, last_update_on }`.

- [ ] **Step 1: Write the data hooks**

`frontend/src/features/dashboard/useDashboard.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { DashboardSummary } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useDashboard() {
  return useQuery({
    queryKey: qk.dashboard.summary(),
    queryFn: () => apiFetch<DashboardSummary>("/dashboard/summary"),
    staleTime: 30_000,
  });
}
```

`frontend/src/features/dashboard/useActivity.ts`:

```ts
import { useInfiniteQuery } from "@tanstack/react-query";
import { apiList } from "@/lib/api/client";
import type { AuditEventOut } from "@/lib/api/types";
import type { Org } from "@/lib/constants";
import { qk } from "@/lib/query";

const PAGE = 20;

/** Paginated global activity feed, optionally filtered by actor org. */
export function useActivity(org: Org | null) {
  return useInfiniteQuery({
    queryKey: qk.activity.list({ org }),
    initialPageParam: 1,
    queryFn: ({ pageParam }) =>
      apiList<AuditEventOut>("/activity", { params: { org, page: pageParam, limit: PAGE } }),
    getNextPageParam: (last, all) => {
      const loaded = all.reduce((n, p) => n + p.data.length, 0);
      return loaded < last.meta.total ? all.length + 1 : undefined;
    },
  });
}
```

- [ ] **Step 2: Write the presentational pieces**

`frontend/src/features/dashboard/StatTiles.tsx`:

```tsx
import { AlertTriangle, Clock, Flag, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";
import type { DashboardSummary } from "@/lib/api/types";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/cn";

function Tile({
  label,
  value,
  to,
  accent,
  icon: Icon,
}: {
  label: string;
  value: number;
  to?: string;
  accent?: string;
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const body = (
    <div className="flex flex-col gap-1 rounded-lg border border-border bg-surface p-4 shadow-sm transition-colors hover:border-border-strong">
      <div className="flex items-center justify-between text-sm text-fg-muted">
        {label}
        {Icon && <Icon className="size-4" />}
      </div>
      <div className={cn("text-2xl font-semibold tabular-nums", accent)} style={{ color: accent }}>
        {value}
      </div>
    </div>
  );
  return to ? (
    <Link to={to} className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg">
      {body}
    </Link>
  ) : (
    body
  );
}

export function StatTiles({ summary }: { summary: DashboardSummary }) {
  const s = summary.open_by_status;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      <Tile label="Open" value={summary.open_total} to="/items" icon={ListChecks} />
      <Tile
        label={STATUS_LABELS.in_progress}
        value={s.in_progress ?? 0}
        to="/items?status=in_progress"
      />
      <Tile label={STATUS_LABELS.blocked} value={s.blocked ?? 0} to="/items?status=blocked" />
      <Tile label="P1" value={summary.open_p1} to="/items?priority=p1" icon={Flag} />
      <Tile
        label="Overdue"
        value={summary.overdue_count}
        accent="var(--danger)"
        icon={AlertTriangle}
      />
      <Tile label="Due soon" value={summary.due_soon_count} accent="var(--warning)" icon={Clock} />
    </div>
  );
}
```

`frontend/src/features/dashboard/NeedsAttention.tsx`:

```tsx
import { Link } from "react-router-dom";
import { DueDate } from "@/components/domain/DueDate";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ItemBrief } from "@/lib/api/types";

function Group({ title, items, empty }: { title: string; items: ItemBrief[]; empty: string }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-medium text-fg-muted">
        {title} <span className="tabular-nums">({items.length})</span>
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-fg-subtle">{empty}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {items.map((i) => (
            <li key={i.id}>
              <Link
                to={`/items/${i.id}`}
                className="flex items-center justify-between gap-3 py-2 text-sm hover:text-accent"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span className="tabular-nums text-fg-subtle">#{i.entry_no}</span>
                  <span className="truncate">{i.title}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <PriorityBadge priority={i.priority} />
                  <DueDate dueOn={i.due_on} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NeedsAttention({
  needs,
}: {
  needs: { overdue: ItemBrief[]; due_soon: ItemBrief[]; stale: ItemBrief[] };
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Needs attention</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <Group title="Overdue" items={needs.overdue} empty="Nothing overdue." />
        <Group title="Due soon" items={needs.due_soon} empty="Nothing due soon." />
        <Group title="Stale (no update)" items={needs.stale} empty="No stale items." />
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/dashboard/Breakdowns.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { OWNER_LABELS } from "@/lib/labels";
import type { OwnerOrg } from "@/lib/constants";

function Bars({ data, labelOf }: { data: Record<string, number>; labelOf?: (k: string) => string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  if (entries.length === 0) return <p className="text-sm text-fg-subtle">No open items.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {entries.map(([key, n]) => (
        <li key={key} className="flex items-center gap-3 text-sm">
          <span className="w-40 shrink-0 truncate text-fg-muted">{labelOf ? labelOf(key) : key}</span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
            <span
              className="block h-full rounded-full bg-accent"
              style={{ width: `${(n / max) * 100}%` }}
            />
          </span>
          <span className="w-8 shrink-0 text-right tabular-nums">{n}</span>
        </li>
      ))}
    </ul>
  );
}

export function Breakdowns({
  byGroup,
  byOwnerOrg,
}: {
  byGroup: Record<string, number>;
  byOwnerOrg: Record<string, number>;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Open items by breakdown</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div>
          <h3 className="mb-2 text-sm font-medium text-fg-muted">By group</h3>
          <Bars data={byGroup} />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-medium text-fg-muted">By owner</h3>
          <Bars data={byOwnerOrg} labelOf={(k) => OWNER_LABELS[k as OwnerOrg] ?? k} />
        </div>
      </CardContent>
    </Card>
  );
}
```

`frontend/src/features/dashboard/ActivityFeed.tsx`:

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { ORG_LABELS } from "@/lib/labels";
import type { Org } from "@/lib/constants";
import { cn } from "@/lib/cn";
import { useActivity } from "./useActivity";

const ORG_TABS: { value: Org | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "gensci", label: "GenSci" },
  { value: "yarrow", label: "Yarrow" },
];

export function ActivityFeed() {
  const [org, setOrg] = useState<Org | null>(null);
  const query = useActivity(org);
  const events = query.data?.pages.flatMap((p) => p.data) ?? [];

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex-row items-center justify-between gap-2">
        <CardTitle>Recent activity</CardTitle>
        <div className="flex gap-1">
          {ORG_TABS.map((t) => (
            <button
              key={t.label}
              onClick={() => setOrg(t.value)}
              className={cn(
                "rounded px-2 py-1 text-xs font-medium",
                org === t.value ? "bg-accent-weak text-accent" : "text-fg-muted hover:bg-surface-2",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {query.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : events.length === 0 ? (
          <p className="text-sm text-fg-subtle">No activity yet.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {events.map((e) => (
              <li key={e.id} className="flex items-start gap-2 text-sm">
                <span
                  className="mt-1.5 size-2 shrink-0 rounded-full"
                  style={{ backgroundColor: `var(--org-${e.actor_org})` }}
                  title={ORG_LABELS[e.actor_org] ?? e.actor_org}
                />
                <span className="min-w-0">
                  <span className="font-medium">{e.actor_name}</span>{" "}
                  <span className="text-fg-muted">{e.summary}</span>{" "}
                  <RelativeTime iso={e.occurred_at} />
                </span>
              </li>
            ))}
          </ul>
        )}
        {query.hasNextPage && (
          <Button
            variant="outline"
            size="sm"
            className="self-start"
            disabled={query.isFetchingNextPage}
            onClick={() => query.fetchNextPage()}
          >
            {query.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 3: Compose the dashboard page**

`frontend/src/features/dashboard/DashboardPage.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";
import { ActivityFeed } from "./ActivityFeed";
import { Breakdowns } from "./Breakdowns";
import { NeedsAttention } from "./NeedsAttention";
import { StatTiles } from "./StatTiles";
import { useDashboard } from "./useDashboard";

export function DashboardPage() {
  const { data, isLoading, isError } = useDashboard();

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }
  if (isError || !data) {
    return <p className="text-sm text-danger">Could not load the dashboard.</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>
      <StatTiles summary={data} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <NeedsAttention needs={data.needs_attention} />
          <Breakdowns byGroup={data.by_group} byOwnerOrg={data.by_owner_org} />
        </div>
        <ActivityFeed />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Route `/dashboard` to the page and make it the post-login default**

In `frontend/src/app/router.tsx`: import `DashboardPage`, remove the `/dashboard` `ComingSoon` stub, add `<Route path="/dashboard" element={<DashboardPage />} />`, and change the index redirect to the dashboard: `<Route index element={<Navigate to="/dashboard" replace />} />`. Also change the login success target and `ProtectedRoute`/`useAuthExpiredRedirect` defaults are fine as-is (they send to `/items` when no `returnTo`; update `LoginPage`'s fallback from `"/items"` to `"/dashboard"` so login lands on the dashboard per §10).

- [ ] **Step 5: Write the failing dashboard test**

`frontend/src/features/dashboard/DashboardPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { DashboardPage } from "./DashboardPage";

function summary() {
  return {
    open_total: 12,
    open_by_status: { in_progress: 4, blocked: 2, open: 6 },
    open_p1: 3,
    overdue_count: 2,
    due_soon_count: 1,
    stale_count: 0,
    needs_attention: {
      overdue: [
        {
          id: 1,
          entry_no: 1,
          title: "Overdue item",
          status: "open",
          priority: "p1",
          owner_org: "gensci",
          due_on: "2026-01-01",
          last_update_on: null,
        },
      ],
      due_soon: [],
      stale: [],
    },
    by_group: { "General Issues": 6, "Gen1 (existing) CMC": 6 },
    by_owner_org: { gensci: 7, yarrow: 5 },
    recent_activity: [],
  };
}

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/dashboard/summary")
      ? { success: true, data: summary(), error: null, meta: null }
      : { success: true, data: [], error: null, meta: { total: 0, page: 1, limit: 20 } };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("renders stat tiles, needs-attention, and breakdowns from the summary", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Overdue item")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument(); // open total tile
  expect(screen.getByText(/needs attention/i)).toBeInTheDocument();
  expect(screen.getByText("By group")).toBeInTheDocument();
});
```

- [ ] **Step 6: Run the test and build**

Run: `cd frontend && npx vitest run src/features/dashboard`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/dashboard frontend/src/app/router.tsx frontend/src/features/auth/LoginPage.tsx
git commit -m "feat(frontend): add dashboard (stat tiles, needs-attention, breakdowns, activity feed)"
# append your session's Co-Authored-By trailer
```

---

### Task 2: Kanban board — columns, optimistic drag-to-change-status, Table/Board toggle

**Files:**
- Modify: `frontend/package.json` (add `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`)
- Create: `frontend/src/features/board/board-columns.ts` (pure grouping/order), `useBoardColumns.ts`
- Create: `frontend/src/features/board/useMoveItemStatus.ts` (optimistic PATCH + rollback)
- Create: `frontend/src/features/board/board-prefs.ts` (collapsed columns, persisted)
- Create: `frontend/src/features/board/BoardCard.tsx`, `BoardColumn.tsx`, `BoardPage.tsx`
- Create: `frontend/src/features/items/ViewToggle.tsx`
- Modify: `frontend/src/app/router.tsx` (route `/board` → `BoardPage`), `frontend/src/features/items/ItemsPage.tsx` (add `<ViewToggle/>`)
- Test: `frontend/src/features/board/board-columns.test.ts`, `useMoveItemStatus.test.tsx`

**Testing note (critical):** do **not** render `DndContext` or perform a drag in jsdom — like Radix overlays it can hang the event loop. Coverage here is the two logic units (`groupIntoColumns` and `useMoveItemStatus`); the actual drag gesture is validated by the Phase 4 Playwright golden-path test.

- [ ] **Step 1: Add the dnd-kit dependencies**

Run: `cd frontend && npm install @dnd-kit/core@^6.3.1 @dnd-kit/sortable@^10.0.0 @dnd-kit/utilities@^3.2.2`
Expected: three packages added, 0 vulnerabilities. (Pin whatever current majors resolve; the API used here — `DndContext`, `useDraggable`, `useDroppable`, `PointerSensor`, `KeyboardSensor` — is stable across these majors.)

- [ ] **Step 2: Write the pure column grouping with a failing test**

`frontend/src/features/board/board-columns.ts`:

```ts
import type { ItemOut } from "@/lib/api/types";
import type { Status } from "@/lib/constants";

/** Board columns, in order; notes are excluded upstream (kind = action only). */
export const BOARD_STATUSES: Status[] = [
  "open",
  "in_progress",
  "blocked",
  "on_hold",
  "completed",
  "cancelled",
];

const PRIORITY_RANK: Record<string, number> = { p1: 0, p2: 1, p3: 2 };

function priorityRank(p: string | null): number {
  return p ? (PRIORITY_RANK[p] ?? 3) : 3;
}

function dueRank(due: string | null): number {
  return due ? new Date(`${due}T00:00:00`).getTime() : Number.POSITIVE_INFINITY;
}

/** Cards ordered by priority (P1 first) then due date (earliest first, undated last). */
export function orderCards(items: ItemOut[]): ItemOut[] {
  return [...items].sort(
    (a, b) => priorityRank(a.priority) - priorityRank(b.priority) || dueRank(a.due_on) - dueRank(b.due_on),
  );
}

export type BoardColumns = Record<Status, ItemOut[]>;

/** Group action items by status into ordered columns. Unknown statuses are ignored. */
export function groupIntoColumns(items: ItemOut[]): BoardColumns {
  const columns = Object.fromEntries(BOARD_STATUSES.map((s) => [s, [] as ItemOut[]])) as BoardColumns;
  for (const item of items) {
    if (item.status && item.status in columns) columns[item.status as Status].push(item);
  }
  for (const s of BOARD_STATUSES) columns[s] = orderCards(columns[s]);
  return columns;
}
```

`frontend/src/features/board/board-columns.test.ts`:

```ts
import type { ItemOut } from "@/lib/api/types";
import { groupIntoColumns, orderCards } from "./board-columns";

function item(o: Partial<ItemOut>): ItemOut {
  return {
    id: 0, program_id: 1, entry_no: 0, kind: "action", title: "t", details: "", group: "G",
    category: null, owner_org: "gensci", assignee_id: null, status: "open", priority: null,
    raised_on: "2026-01-01", source: null, due_on: null, completed_on: null, notes_risks: "",
    file_path: "", created_by: 1, created_at: "2026-01-01T00:00:00", updated_by: 1,
    updated_at: "2026-01-01T00:00:00", deleted_at: null, last_update_on: null, ...o,
  };
}

test("groups by status and skips unknown/absent statuses", () => {
  const cols = groupIntoColumns([
    item({ id: 1, status: "open" }),
    item({ id: 2, status: "blocked" }),
    item({ id: 3, status: null }), // a note-like row; ignored
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
```

Run: `cd frontend && npx vitest run src/features/board/board-columns.test.ts` → RED then GREEN.

- [ ] **Step 3: Write the board data hook and preferences**

`frontend/src/features/board/useBoardColumns.ts`:

```ts
import { useItems } from "@/features/items/useItems";
import type { ItemFilters } from "@/features/items/filters";
import { groupIntoColumns } from "./board-columns";

/** Fetch all matching action items (no paging) and group them into columns. */
export function useBoardColumns(filters: ItemFilters) {
  const query = useItems({ ...filters, kind: "action", status: [], page: 1, limit: 200 });
  const items = query.data?.data ?? [];
  return { ...query, columns: groupIntoColumns(items), total: query.data?.meta.total ?? 0 };
}
```

`frontend/src/features/board/board-prefs.ts`:

```ts
import { useCallback, useState } from "react";

const KEY = "cmc-board-collapsed";
const DEFAULT = ["completed", "cancelled"];

export function useCollapsedColumns() {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(KEY);
      return new Set(raw ? (JSON.parse(raw) as string[]) : DEFAULT);
    } catch {
      return new Set(DEFAULT);
    }
  });
  const toggle = useCallback((status: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      try {
        localStorage.setItem(KEY, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);
  return { collapsed, toggle };
}
```

- [ ] **Step 4: Write the optimistic status-move hook with a failing test**

`frontend/src/features/board/useMoveItemStatus.ts`:

```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ItemOut, Meta } from "@/lib/api/types";
import type { Status } from "@/lib/constants";
import { qk } from "@/lib/query";

type ListCache = { data: ItemOut[]; meta: Meta };

/** Move a card to a new status with an optimistic cache update and rollback on error. */
export function useMoveItemStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: Status }) =>
      apiFetch<ItemOut>(`/items/${id}`, { method: "PATCH", body: { status } }),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: qk.items.all() });
      const snapshot = qc.getQueriesData<ListCache>({ queryKey: ["items", "list"] });
      for (const [key, value] of snapshot) {
        if (!value) continue;
        qc.setQueryData<ListCache>(key, {
          ...value,
          data: value.data.map((it) => (it.id === id ? { ...it, status } : it)),
        });
      }
      return { snapshot };
    },
    onError: (_err, _vars, ctx) => {
      ctx?.snapshot.forEach(([key, value]) => qc.setQueryData(key, value));
    },
    onSettled: () => qc.invalidateQueries({ queryKey: qk.items.all() }),
  });
}
```

`frontend/src/features/board/useMoveItemStatus.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ItemOut } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { useMoveItemStatus } from "./useMoveItemStatus";

function item(id: number, status: string): ItemOut {
  return {
    id, program_id: 1, entry_no: id, kind: "action", title: "t", details: "", group: "G",
    category: null, owner_org: "gensci", assignee_id: null, status, priority: null,
    raised_on: "2026-01-01", source: null, due_on: null, completed_on: null, notes_risks: "",
    file_path: "", created_by: 1, created_at: "2026-01-01T00:00:00", updated_by: 1,
    updated_at: "2026-01-01T00:00:00", deleted_at: null, last_update_on: null,
  } as ItemOut;
}

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  qc.setQueryData(qk.items.list({ any: true }), { data: [item(1, "open")], meta: { total: 1, page: 1, limit: 50 } });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
  return { qc, wrapper };
}

const cachedStatus = (qc: QueryClient) =>
  qc.getQueryData<{ data: ItemOut[] }>(qk.items.list({ any: true }))!.data[0].status;

afterEach(() => vi.restoreAllMocks());

test("optimistically updates the cached card status", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ success: true, data: item(1, "blocked"), error: null, meta: null }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const { qc, wrapper } = setup();
  const { result } = renderHook(() => useMoveItemStatus(), { wrapper });
  result.current.mutate({ id: 1, status: "blocked" });
  await waitFor(() => expect(cachedStatus(qc)).toBe("blocked"));
});

test("rolls back the cached status when the request fails", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ success: false, data: null, error: { code: "conflict", message: "no" }, meta: null }),
      { status: 409, headers: { "Content-Type": "application/json" } },
    ),
  );
  const { qc, wrapper } = setup();
  const { result } = renderHook(() => useMoveItemStatus(), { wrapper });
  result.current.mutate({ id: 1, status: "blocked" });
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(cachedStatus(qc)).toBe("open"); // rolled back
});
```

Run: `cd frontend && npx vitest run src/features/board/useMoveItemStatus.test.tsx` → RED then GREEN (`2 passed`).

- [ ] **Step 5: Write the card, column, and board page (dnd-kit)**

`frontend/src/features/board/BoardCard.tsx`:

```tsx
import { useDraggable } from "@dnd-kit/core";
import { useNavigate } from "react-router-dom";
import { DueDate } from "@/components/domain/DueDate";
import { OwnerBadge } from "@/components/domain/OwnerBadge";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import type { ItemOut } from "@/lib/api/types";
import { cn } from "@/lib/cn";

export function BoardCard({ item }: { item: ItemOut }) {
  const navigate = useNavigate();
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({ id: item.id });
  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onClick={() => navigate(`/items?selected=${item.id}`)}
      className={cn(
        "cursor-grab rounded-md border border-border bg-surface p-3 shadow-sm active:cursor-grabbing",
        isDragging && "opacity-50",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs tabular-nums text-fg-subtle">#{item.entry_no}</span>
        <PriorityBadge priority={item.priority} />
      </div>
      <p className="mt-1 line-clamp-2 text-sm font-medium">{item.title}</p>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs">
        <OwnerBadge owner={item.owner_org} />
        <DueDate dueOn={item.due_on} />
      </div>
    </div>
  );
}
```

`frontend/src/features/board/BoardColumn.tsx`:

```tsx
import { useDroppable } from "@dnd-kit/core";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { ItemOut } from "@/lib/api/types";
import type { Status } from "@/lib/constants";
import { STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/lib/cn";
import { BoardCard } from "./BoardCard";

export function BoardColumn({
  status,
  items,
  collapsed,
  onToggle,
}: {
  status: Status;
  items: ItemOut[];
  collapsed: boolean;
  onToggle: () => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <div
      ref={setNodeRef}
      className={cn(
        "flex w-72 shrink-0 flex-col rounded-lg border border-border bg-surface-2/40",
        isOver && "ring-2 ring-ring",
      )}
    >
      <button
        onClick={onToggle}
        className="flex items-center justify-between gap-2 px-3 py-2 text-sm font-medium"
      >
        <span className="flex items-center gap-1.5">
          <span className="size-2 rounded-full" style={{ backgroundColor: `var(--status-${status})` }} />
          {STATUS_LABELS[status]}
          <span className="tabular-nums text-fg-subtle">{items.length}</span>
        </span>
        {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
      </button>
      {!collapsed && (
        <div className="flex flex-1 flex-col gap-2 p-2 pt-0">
          {items.map((item) => (
            <BoardCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
```

`frontend/src/features/board/BoardPage.tsx`:

```tsx
import { useMemo } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { useSearchParams } from "react-router-dom";
import { Skeleton } from "@/components/ui/skeleton";
import { FilterBar } from "@/features/items/FilterBar";
import { ViewToggle } from "@/features/items/ViewToggle";
import { ItemDetailSheet } from "@/features/item-detail/ItemDetailSheet";
import {
  filtersToSearchParams,
  parseFilters,
  type ItemFilters,
} from "@/features/items/filters";
import { useToast } from "@/lib/toast";
import { BOARD_STATUSES } from "./board-columns";
import { BoardColumn } from "./BoardColumn";
import { useBoardColumns } from "./useBoardColumns";
import { useCollapsedColumns } from "./board-prefs";
import { useMoveItemStatus } from "./useMoveItemStatus";

export function BoardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const board = useBoardColumns(filters);
  const { collapsed, toggle } = useCollapsedColumns();
  const move = useMoveItemStatus();
  const { toast } = useToast();
  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor));

  function apply(next: Partial<ItemFilters>) {
    const params = filtersToSearchParams({ ...filters, ...next, page: 1 });
    const selected = searchParams.get("selected");
    if (selected) params.set("selected", selected);
    setSearchParams(params);
  }

  function onDragEnd(event: DragEndEvent) {
    const id = Number(event.active.id);
    const target = event.over?.id as string | undefined;
    if (!target || !BOARD_STATUSES.includes(target as never)) return;
    const current = board.columns;
    const from = BOARD_STATUSES.find((s) => current[s].some((i) => i.id === id));
    if (!from || from === target) return;
    move.mutate(
      { id, status: target as never },
      { onError: () => toast({ title: "Could not move the card", variant: "error" }) },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Board</h1>
        <ViewToggle />
      </div>
      <FilterBar filters={filters} onChange={apply} />
      {board.isLoading ? (
        <Skeleton className="h-96 w-full" />
      ) : (
        <DndContext sensors={sensors} onDragEnd={onDragEnd}>
          <div className="flex gap-3 overflow-x-auto pb-4">
            {BOARD_STATUSES.map((status) => (
              <BoardColumn
                key={status}
                status={status}
                items={board.columns[status]}
                collapsed={collapsed.has(status)}
                onToggle={() => toggle(status)}
              />
            ))}
          </div>
        </DndContext>
      )}
      <ItemDetailSheet />
    </div>
  );
}
```

- [ ] **Step 6: Write the Table/Board toggle and wire it in**

`frontend/src/features/items/ViewToggle.tsx`:

```tsx
import { LayoutGrid, Table2 } from "lucide-react";
import { NavLink, useSearchParams } from "react-router-dom";
import { cn } from "@/lib/cn";

const KEY = "cmc-items-view";

/** Persist the last chosen view so the sidebar returns the user where they left off. */
export function rememberView(view: "table" | "board") {
  try {
    localStorage.setItem(KEY, view);
  } catch {
    /* ignore */
  }
}

export function lastView(): "table" | "board" {
  try {
    return localStorage.getItem(KEY) === "board" ? "board" : "table";
  } catch {
    return "table";
  }
}

export function ViewToggle() {
  const [params] = useSearchParams();
  const qs = params.toString();
  const suffix = qs ? `?${qs}` : "";
  const link = (to: string, active: boolean, Icon: typeof Table2, label: string) => (
    <NavLink
      to={`${to}${suffix}`}
      onClick={() => rememberView(to === "/board" ? "board" : "table")}
      className={cn(
        "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm font-medium",
        active ? "bg-accent-weak text-accent" : "text-fg-muted hover:bg-surface-2",
      )}
    >
      <Icon className="size-4" />
      {label}
    </NavLink>
  );
  return (
    <div className="inline-flex rounded-md border border-border p-0.5">
      {link("/items", location.pathname.startsWith("/items"), Table2, "Table")}
      {link("/board", location.pathname.startsWith("/board"), LayoutGrid, "Board")}
    </div>
  );
}
```

In `frontend/src/features/items/ItemsPage.tsx`: import `ViewToggle` and render it in the header row next to the title, e.g. wrap the `<h1>`/count block and `<ViewToggle />` in a `flex items-center justify-between` div.

In `frontend/src/app/router.tsx`: import `BoardPage`, remove the `/board` `ComingSoon` stub, add `<Route path="/board" element={<BoardPage />} />`.

- [ ] **Step 7: Run the logic tests and build**

Run: `cd frontend && npx vitest run src/features/board`
Expected: PASS (`board-columns` 2 + `useMoveItemStatus` 2 = 4).

Run: `cd frontend && npm run build`
Expected: clean. (No board render test — the drag gesture is a Phase 4 Playwright case.)

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/features/board \
  frontend/src/features/items/ViewToggle.tsx frontend/src/features/items/ItemsPage.tsx \
  frontend/src/app/router.tsx
git commit -m "feat(frontend): add Kanban board with optimistic drag-to-change-status and Table/Board toggle"
# append your session's Co-Authored-By trailer
```

---

### Task 3: Admin shell, route guard, and Users & Invitations

**Files:**
- Modify: `frontend/src/lib/query.ts` (add `users.admin`, `invitations.list` keys), `frontend/src/lib/api/types.ts` (add `InvitationCreatedOut`, `ResetLinkOut`)
- Create: `frontend/src/app/AdminRoute.tsx`, `NotAuthorised.tsx`
- Create: `frontend/src/components/ui/copy-button.tsx`
- Create: `frontend/src/features/admin/AdminLayout.tsx`
- Create: `frontend/src/features/admin/users/useUsersAdmin.ts`, `UsersPage.tsx`, `UserRow.tsx`, `InviteDialog.tsx`, `ResetLinkDialog.tsx`
- Modify: `frontend/src/app/router.tsx` (admin routes under the guard)
- Test: `frontend/src/features/admin/users/UsersPage.test.tsx`

Reminder: user creation is via **invitations** (there is no `POST /users`). Admin "add user" = create an invitation and hand over the one-time link.

- [ ] **Step 1: Extend query keys and DTO aliases**

In `frontend/src/lib/query.ts`, change the `users` and add an `invitations` entry:

```ts
  users: { list: () => ["users"] as const, admin: () => ["users", "admin"] as const },
  invitations: { list: () => ["invitations"] as const },
```

In `frontend/src/lib/api/types.ts`, add:

```ts
export type InvitationCreatedOut = S["InvitationCreatedOut"];
export type ResetLinkOut = S["ResetLinkOut"];
```

- [ ] **Step 2: Write the guard, the not-authorised page, and a copy button**

`frontend/src/app/NotAuthorised.tsx`:

```tsx
import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";

export function NotAuthorised() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-lg font-semibold">Admins only</p>
      <p className="text-fg-muted">You do not have permission to view this page.</p>
      <Link to="/dashboard" className={buttonVariants({ variant: "outline" })}>
        Back to dashboard
      </Link>
    </div>
  );
}
```

`frontend/src/app/AdminRoute.tsx`:

```tsx
import { Outlet } from "react-router-dom";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/features/auth/useAuth";
import { NotAuthorised } from "./NotAuthorised";

/** Nested inside ProtectedRoute; the user is authenticated, so this only checks the role. */
export function AdminRoute() {
  const { user, isFetched } = useAuth();
  if (!isFetched) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner className="size-6" />
      </div>
    );
  }
  return user?.role === "admin" ? <Outlet /> : <NotAuthorised />;
}
```

`frontend/src/components/ui/copy-button.tsx`:

```tsx
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(value);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      {copied ? "Copied" : label}
    </Button>
  );
}
```

- [ ] **Step 3: Write the admin data hooks**

`frontend/src/features/admin/users/useUsersAdmin.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type {
  InvitationCreatedOut,
  InvitationOut,
  ResetLinkOut,
  UserOut,
} from "@/lib/api/types";
import type { Org, Role } from "@/lib/constants";
import { qk } from "@/lib/query";

export function useUsersList() {
  return useQuery({ queryKey: qk.users.admin(), queryFn: () => apiFetch<UserOut[]>("/users") });
}

export function useInvitations() {
  return useQuery({
    queryKey: qk.invitations.list(),
    queryFn: () => apiFetch<InvitationOut[]>("/invitations"),
  });
}

export function usePatchUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<{ org: Org; role: Role; is_active: boolean; name: string }> }) =>
      apiFetch<UserOut>(`/users/${id}`, { method: "PATCH", body: patch }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.users.admin() }),
  });
}

export function useCreateInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; org: Org; role: Role }) =>
      apiFetch<InvitationCreatedOut>("/invitations", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.invitations.list() }),
  });
}

export function useRevokeInvitation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<InvitationOut>(`/invitations/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.invitations.list() }),
  });
}

export function useResetLink() {
  return useMutation({
    mutationFn: (userId: number) =>
      apiFetch<ResetLinkOut>(`/users/${userId}/reset-link`, { method: "POST" }),
  });
}
```

- [ ] **Step 4: Write the admin layout**

`frontend/src/features/admin/AdminLayout.tsx`:

```tsx
import { NavLink, Outlet } from "react-router-dom";
import { cn } from "@/lib/cn";

const TABS = [
  { to: "/admin/users", label: "Users & invitations" },
  { to: "/admin/vocab", label: "Vocabularies" },
  { to: "/admin/import", label: "Import" },
  { to: "/admin/export", label: "Export" },
];

export function AdminLayout() {
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-xl font-semibold">Admin</h1>
      <nav className="flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <NavLink
            key={t.to}
            to={t.to}
            className={({ isActive }) =>
              cn(
                "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
                isActive
                  ? "border-accent text-fg"
                  : "border-transparent text-fg-muted hover:text-fg",
              )
            }
          >
            {t.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
```

- [ ] **Step 5: Write the user row, invite dialog, reset-link dialog, and users page**

`frontend/src/features/admin/users/UserRow.tsx`:

```tsx
import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { UserOut } from "@/lib/api/types";
import { ORGS, ROLES } from "@/lib/constants";
import { ORG_LABELS } from "@/lib/labels";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { usePatchUser } from "./useUsersAdmin";

export function UserRow({ user, onResetLink }: { user: UserOut; onResetLink: (u: UserOut) => void }) {
  const patch = usePatchUser();
  return (
    <tr className="border-b border-border/60 last:border-0">
      <td className="px-4 py-3">
        <div className="font-medium">{user.name}</div>
        <div className="text-xs text-fg-muted">{user.email}</div>
      </td>
      <td className="px-4 py-3">
        <Select
          value={user.org}
          onValueChange={(org) => patch.mutate({ id: user.id, patch: { org: org as never } })}
        >
          <SelectTrigger className="h-8 w-32"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ORGS.map((o) => <SelectItem key={o} value={o}>{ORG_LABELS[o]}</SelectItem>)}
          </SelectContent>
        </Select>
      </td>
      <td className="px-4 py-3">
        <Select
          value={user.role}
          onValueChange={(role) => patch.mutate({ id: user.id, patch: { role: role as never } })}
        >
          <SelectTrigger className="h-8 w-28"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ROLES.map((r) => <SelectItem key={r} value={r}>{r === "admin" ? "Admin" : "Member"}</SelectItem>)}
          </SelectContent>
        </Select>
      </td>
      <td className="px-4 py-3">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={user.is_active}
            onCheckedChange={(v) => patch.mutate({ id: user.id, patch: { is_active: !!v } })}
          />
          {user.is_active ? "Active" : "Inactive"}
        </label>
      </td>
      <td className="px-4 py-3 text-sm text-fg-muted">
        <RelativeTime iso={user.last_login_at} />
      </td>
      <td className="px-4 py-3 text-right">
        <Button variant="outline" size="sm" onClick={() => onResetLink(user)}>
          <KeyRound className="size-4" /> Reset link
        </Button>
      </td>
    </tr>
  );
}
```

`frontend/src/features/admin/users/ResetLinkDialog.tsx`:

```tsx
import { useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { CopyButton } from "@/components/ui/copy-button";
import { Spinner } from "@/components/ui/spinner";
import type { UserOut } from "@/lib/api/types";
import { useResetLink } from "./useUsersAdmin";

/** Opens when `user` is set; requests a one-time reset link and shows it to copy. */
export function ResetLinkDialog({ user, onClose }: { user: UserOut | null; onClose: () => void }) {
  const reset = useResetLink();
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setUrl(null);
      return;
    }
    reset.mutate(user.id, { onSuccess: (data) => setUrl(data.url) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  return (
    <Dialog open={!!user} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Password reset link</DialogTitle>
          <DialogDescription>
            Send this one-time link to {user?.name}. It expires and can be used once.
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 px-6 py-4">
          {url ? (
            <>
              <Input readOnly value={url} className="font-mono text-xs" />
              <CopyButton value={url} />
            </>
          ) : reset.isError ? (
            <p className="text-sm text-danger">Could not create a reset link.</p>
          ) : (
            <Spinner />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

`frontend/src/features/admin/users/InviteDialog.tsx`:

```tsx
import { useState } from "react";
import { UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CopyButton } from "@/components/ui/copy-button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api/client";
import { ORGS, ROLES, type Org, type Role } from "@/lib/constants";
import { ORG_LABELS } from "@/lib/labels";
import { useCreateInvitation } from "./useUsersAdmin";

export function InviteDialog() {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [org, setOrg] = useState<Org>("gensci");
  const [role, setRole] = useState<Role>("member");
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const create = useCreateInvitation();

  function reset() {
    setEmail("");
    setOrg("gensci");
    setRole("member");
    setUrl(null);
    setError(null);
  }

  async function submit() {
    setError(null);
    try {
      const result = await create.mutateAsync({ email, org, role });
      setUrl(result.url);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the invitation.");
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button size="sm">
          <UserPlus className="size-4" /> Invite user
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invite a user</DialogTitle>
        </DialogHeader>
        {url ? (
          <div className="flex flex-col gap-3 px-6 py-4">
            <p className="text-sm text-fg-muted">
              Invitation created. Send this one-time link to {email}:
            </p>
            <div className="flex items-center gap-2">
              <Input readOnly value={url} className="font-mono text-xs" />
              <CopyButton value={url} />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4 px-6 py-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="invite-email">Email</Label>
              <Input
                id="invite-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-1.5">
                <Label>Org</Label>
                <Select value={org} onValueChange={(v) => setOrg(v as Org)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ORGS.map((o) => <SelectItem key={o} value={o}>{ORG_LABELS[o]}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label>Role</Label>
                <Select value={role} onValueChange={(v) => setRole(v as Role)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {ROLES.map((r) => (
                      <SelectItem key={r} value={r}>{r === "admin" ? "Admin" : "Member"}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
          </div>
        )}
        {!url && (
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={!email.trim() || create.isPending} onClick={submit}>
              Create invitation
            </Button>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

`frontend/src/features/admin/users/UsersPage.tsx`:

```tsx
import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CopyButton } from "@/components/ui/copy-button";
import { Skeleton } from "@/components/ui/skeleton";
import { RelativeTime } from "@/components/domain/RelativeTime";
import type { UserOut } from "@/lib/api/types";
import { ORG_LABELS } from "@/lib/labels";
import { InviteDialog } from "./InviteDialog";
import { ResetLinkDialog } from "./ResetLinkDialog";
import { UserRow } from "./UserRow";
import { useInvitations, useRevokeInvitation, useUsersList } from "./useUsersAdmin";

export function UsersPage() {
  const users = useUsersList();
  const invitations = useInvitations();
  const revoke = useRevokeInvitation();
  const [resetUser, setResetUser] = useState<UserOut | null>(null);
  const pending = (invitations.data ?? []).filter((i) => !i.accepted_at);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Users</h2>
        <InviteDialog />
      </div>

      <div className="overflow-x-auto rounded-lg border border-border bg-surface">
        {users.isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-fg-muted">
                <th className="px-4 py-2.5 font-medium">User</th>
                <th className="px-4 py-2.5 font-medium">Org</th>
                <th className="px-4 py-2.5 font-medium">Role</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Last login</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {(users.data ?? []).map((u) => (
                <UserRow key={u.id} user={u} onResetLink={setResetUser} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Pending invitations</CardTitle>
        </CardHeader>
        <CardContent>
          {pending.length === 0 ? (
            <p className="text-sm text-fg-subtle">No pending invitations.</p>
          ) : (
            <ul className="flex flex-col divide-y divide-border">
              {pending.map((inv) => (
                <li key={inv.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span>
                    <span className="font-medium">{inv.email}</span>{" "}
                    <span className="text-fg-muted">
                      · {ORG_LABELS[inv.org ?? ""] ?? inv.org} · expires <RelativeTime iso={inv.expires_at} />
                    </span>
                  </span>
                  <span className="flex items-center gap-2">
                    <CopyButton value={`${window.location.origin}/accept-invite?token=…`} label="Link" />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => revoke.mutate(inv.id)}
                      aria-label={`Revoke invitation for ${inv.email}`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <ResetLinkDialog user={resetUser} onClose={() => setResetUser(null)} />
    </div>
  );
}
```

> **Note on the pending-invitation link:** `GET /invitations` returns invitation metadata but **not** the raw token (it's stored hashed), so the full accept URL is only available once, from the `POST /invitations` response shown in the InviteDialog. The pending list therefore cannot reconstruct the link — the `CopyButton` above is a placeholder showing that limitation. Either (a) drop the per-row copy and rely on the create-time link, or (b) treat "re-issue link" as a reset-style action. **Recommended:** remove the placeholder CopyButton from pending rows and keep only Revoke; the create dialog is the single source of the link. Implement option (a).

- [ ] **Step 6: Wire the admin routes under the guard**

In `frontend/src/app/router.tsx`: import `AdminRoute`, `AdminLayout`, `UsersPage`; remove the `/admin` `ComingSoon` stub; add:

```tsx
<Route path="/admin" element={<AdminRoute />}>
  <Route element={<AdminLayout />}>
    <Route index element={<Navigate to="/admin/users" replace />} />
    <Route path="users" element={<UsersPage />} />
    {/* vocab, import, export routes added in Tasks 4–5 */}
  </Route>
</Route>
```

Also show the Admin nav item only to admins: in `frontend/src/app/layout/Sidebar.tsx`, read `useAuth()` and filter out the `/admin` entry when `user?.role !== "admin"`.

- [ ] **Step 7: Write the failing users-page test (render-only; no dialogs opened)**

`frontend/src/features/admin/users/UsersPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ToastProvider } from "@/lib/toast";
import { UsersPage } from "./UsersPage";

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = { success: true, data: [], error: null, meta: null };
    if (url.endsWith("/api/users")) {
      body = {
        success: true,
        data: [
          {
            id: 1, email: "ada@gensci.example", name: "Ada Admin", org: "gensci", role: "admin",
            is_active: true, last_login_at: "2026-02-01T00:00:00", created_at: "2026-01-01T00:00:00",
          },
        ],
        error: null, meta: null,
      };
    } else if (url.includes("/invitations")) {
      body = {
        success: true,
        data: [
          {
            id: 9, purpose: "invite", email: "mo@yarrow.example", org: "yarrow", role: "member",
            user_id: null, expires_at: "2030-01-01T00:00:00", accepted_at: null, created_by: 1,
            created_at: "2026-02-01T00:00:00",
          },
        ],
        error: null, meta: null,
      };
    }
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("lists users and pending invitations", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <MemoryRouter>
          <UsersPage />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Ada Admin")).toBeInTheDocument();
  expect(await screen.findByText("mo@yarrow.example")).toBeInTheDocument();
});
```

- [ ] **Step 8: Run the test and build**

Run: `cd frontend && npx vitest run src/features/admin/users`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/query.ts frontend/src/lib/api/types.ts frontend/src/app/AdminRoute.tsx \
  frontend/src/app/NotAuthorised.tsx frontend/src/components/ui/copy-button.tsx \
  frontend/src/features/admin frontend/src/app/router.tsx frontend/src/app/layout/Sidebar.tsx
git commit -m "feat(frontend): add admin shell, route guard, and users & invitations screen"
# append your session's Co-Authored-By trailer
```

---

### Task 4: Admin — vocabulary management (add, rename, reorder, deactivate)

**Files:**
- Create: `frontend/src/features/admin/vocab/useVocabAdmin.ts`, `VocabPage.tsx`, `VocabFieldTable.tsx`, `AddTermRow.tsx`
- Modify: `frontend/src/features/items/useVocab.ts` (pickers show only active terms — spec §8)
- Modify: `frontend/src/app/router.tsx` (route `/admin/vocab`)
- Test: `frontend/src/features/admin/vocab/VocabPage.test.tsx`

Renaming a term PATCHes its `value`; the backend rewrites existing items in one audited op. Reordering swaps `sort_order` with the neighbour. Deactivating PATCHes `is_active=false` (kept valid on old items, hidden from pickers).

- [ ] **Step 1: Filter pickers to active terms**

In `frontend/src/features/items/useVocab.ts`, change the `pick` helper to exclude inactive terms:

```ts
  const pick = (field: "group" | "category") =>
    terms
      .filter((t) => t.field === field && t.is_active)
      .sort((a, b) => a.sort_order - b.sort_order || a.value.localeCompare(b.value));
```

(The admin screen below fetches the same `qk.vocab.list()` cache but keeps inactive terms visible.)

- [ ] **Step 2: Write the admin vocab hook**

`frontend/src/features/admin/vocab/useVocabAdmin.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { VocabTermOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

type Field = "group" | "category";

export function useVocabAdmin() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: qk.vocab.list(),
    queryFn: () => apiFetch<VocabTermOut[]>("/vocab"),
  });
  const terms = query.data ?? [];
  const byField = (f: Field) =>
    terms
      .filter((t) => t.field === f)
      .sort((a, b) => a.sort_order - b.sort_order || a.value.localeCompare(b.value));
  const invalidate = () => qc.invalidateQueries({ queryKey: qk.vocab.list() });

  const create = useMutation({
    mutationFn: (body: { field: Field; value: string; sort_order: number }) =>
      apiFetch<VocabTermOut>("/vocab", { method: "POST", body }),
    onSuccess: invalidate,
  });
  const patch = useMutation({
    mutationFn: ({ id, ...body }: { id: number; value?: string; sort_order?: number; is_active?: boolean }) =>
      apiFetch<VocabTermOut>(`/vocab/${id}`, { method: "PATCH", body }),
    onSuccess: invalidate,
  });

  return { ...query, groups: byField("group"), categories: byField("category"), create, patch };
}
```

- [ ] **Step 3: Write the field table, add-term row, and page**

`frontend/src/features/admin/vocab/AddTermRow.tsx`:

```tsx
import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AddTermRow({ onAdd, pending }: { onAdd: (value: string) => void; pending: boolean }) {
  const [value, setValue] = useState("");
  return (
    <div className="flex items-center gap-2">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="New term…"
        className="h-8 w-56"
        onKeyDown={(e) => {
          if (e.key === "Enter" && value.trim()) {
            onAdd(value.trim());
            setValue("");
          }
        }}
      />
      <Button
        size="sm"
        disabled={!value.trim() || pending}
        onClick={() => {
          onAdd(value.trim());
          setValue("");
        }}
      >
        <Plus className="size-4" /> Add
      </Button>
    </div>
  );
}
```

`frontend/src/features/admin/vocab/VocabFieldTable.tsx`:

```tsx
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
              <Button variant="ghost" size="icon" className="h-8 w-8" aria-label="Cancel" onClick={() => setEditing(null)}>
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
```

`frontend/src/features/admin/vocab/VocabPage.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";
import type { VocabTermOut } from "@/lib/api/types";
import { AddTermRow } from "./AddTermRow";
import { VocabFieldTable } from "./VocabFieldTable";
import { useVocabAdmin } from "./useVocabAdmin";

export function VocabPage() {
  const vocab = useVocabAdmin();

  const rename = (id: number, value: string) => vocab.patch.mutate({ id, value });
  const setActive = (id: number, is_active: boolean) => vocab.patch.mutate({ id, is_active });
  const swap = (a: VocabTermOut, b: VocabTermOut) => {
    vocab.patch.mutate({ id: a.id, sort_order: b.sort_order });
    vocab.patch.mutate({ id: b.id, sort_order: a.sort_order });
  };

  if (vocab.isLoading) return <Skeleton className="h-64 w-full" />;

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
      {(["group", "category"] as const).map((field) => {
        const terms = field === "group" ? vocab.groups : vocab.categories;
        return (
          <section key={field} className="flex flex-col gap-3">
            <h2 className="text-base font-semibold capitalize">{field === "group" ? "Groups" : "Categories"}</h2>
            <VocabFieldTable terms={terms} onRename={rename} onSetActive={setActive} onSwap={swap} />
            <AddTermRow
              pending={vocab.create.isPending}
              onAdd={(value) =>
                vocab.create.mutate({ field, value, sort_order: (terms.at(-1)?.sort_order ?? 0) + 1 })
              }
            />
          </section>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Add the route**

In `frontend/src/app/router.tsx`, add under the admin `AdminLayout` children: `<Route path="vocab" element={<VocabPage />} />` (import `VocabPage`).

- [ ] **Step 5: Write the failing vocab test (render + add term via plain input; no overlays)**

`frontend/src/features/admin/vocab/VocabPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VocabPage } from "./VocabPage";

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.includes("/vocab") && method === "POST") {
      return new Response(
        JSON.stringify({
          success: true,
          data: { id: 99, program_id: 1, field: "group", value: "New Group", sort_order: 3, is_active: true },
          error: null,
          meta: null,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      );
    }
    const body = {
      success: true,
      data: [
        { id: 1, program_id: 1, field: "group", value: "General Issues", sort_order: 0, is_active: true },
        { id: 2, program_id: 1, field: "category", value: "QA", sort_order: 0, is_active: true },
      ],
      error: null,
      meta: null,
    };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("lists terms per field and posts a new one", async () => {
  const fetchSpy = mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <VocabPage />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("General Issues")).toBeInTheDocument();
  expect(screen.getByText("QA")).toBeInTheDocument();

  const [groupAdd] = screen.getAllByPlaceholderText(/new term/i);
  await userEvent.type(groupAdd, "New Group");
  await userEvent.click(screen.getAllByRole("button", { name: /add/i })[0]);
  await waitFor(() =>
    expect(
      fetchSpy.mock.calls.some(([u, i]) => String(u).includes("/vocab") && (i?.method ?? "GET") === "POST"),
    ).toBe(true),
  );
});
```

- [ ] **Step 6: Run the test and build**

Run: `cd frontend && npx vitest run src/features/admin/vocab`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/admin/vocab frontend/src/features/items/useVocab.ts frontend/src/app/router.tsx
git commit -m "feat(frontend): add vocabulary admin (add, rename, reorder, deactivate)"
# append your session's Co-Authored-By trailer
```

---

### Task 5: Admin — Excel import (preview → commit) and export

**Files:**
- Modify: `frontend/src/lib/api/client.ts` (add `apiUpload` for multipart), `frontend/src/lib/api/types.ts` (add `ImportPreviewOut`, `ImportCommitOut`)
- Create: `frontend/src/lib/download.ts`
- Create: `frontend/src/features/admin/import/useImport.ts`, `UnmappedPicker.tsx`, `PreviewTable.tsx`, `ImportPage.tsx`
- Create: `frontend/src/features/items/ExportButton.tsx`, `frontend/src/features/admin/export/ExportPage.tsx`
- Modify: `frontend/src/features/items/ItemsPage.tsx` (Export button in the toolbar), `frontend/src/app/router.tsx` (`/admin/import`, `/admin/export`)
- Test: `frontend/src/features/admin/import/ImportPage.test.tsx`

Import endpoints are multipart (`file` + `overrides` JSON string). Export is a binary GET reusing the item filter params; it's allowed for any authenticated user (spec §6), so the Export button also lives on the items toolbar, not only in admin.

- [ ] **Step 1: Add the multipart client call and DTO aliases**

Append to `frontend/src/lib/api/client.ts`:

```ts
/** POST multipart form data (file uploads). Lets the browser set the multipart boundary. */
export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "X-Requested-With": "fetch" },
    credentials: "same-origin",
    body: formData,
  });
  if (response.status === 401) window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
  let envelope: Envelope<T>;
  try {
    envelope = (await response.json()) as Envelope<T>;
  } catch {
    throw new ApiError(response.status, {
      code: "network_error",
      message: "The server returned an unreadable response.",
    });
  }
  if (!response.ok || !envelope.success) {
    throw new ApiError(response.status, envelope.error ?? { code: "error", message: "Request failed" });
  }
  return envelope.data as T;
}
```

Add to `frontend/src/lib/api/types.ts`:

```ts
export type ImportPreviewOut = S["ImportPreviewOut"];
export type ImportCommitOut = S["ImportCommitOut"];
```

- [ ] **Step 2: Write the download helper**

`frontend/src/lib/download.ts`:

```ts
/** Trigger a browser download of the export endpoint. Cookie-authenticated, same-origin GET;
 * the server sets Content-Disposition, so a transient anchor is enough. */
export function downloadExport(params: URLSearchParams): void {
  const qs = params.toString();
  const a = document.createElement("a");
  a.href = `/api/export/excel${qs ? `?${qs}` : ""}`;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
```

- [ ] **Step 3: Write the import hooks**

`frontend/src/features/admin/import/useImport.ts`:

```ts
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
```

- [ ] **Step 4: Write the unmapped picker and preview table**

`frontend/src/features/admin/import/UnmappedPicker.tsx`:

```tsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export interface FieldOption {
  value: string;
  label: string;
}

/** One <select> per raw value that could not be mapped, writing into the overrides map. */
export function UnmappedPicker({
  title,
  rawValues,
  options,
  mapping,
  onMap,
}: {
  title: string;
  rawValues: string[];
  options: FieldOption[];
  mapping: Record<string, string>;
  onMap: (raw: string, target: string) => void;
}) {
  if (rawValues.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-sm font-medium text-fg-muted">{title}</h3>
      <ul className="flex flex-col gap-2">
        {rawValues.map((raw) => (
          <li key={raw} className="flex items-center gap-3 text-sm">
            <code className="w-48 shrink-0 truncate rounded bg-surface-2 px-1.5 py-0.5">{raw || "(blank)"}</code>
            <span className="text-fg-subtle">→</span>
            <Select value={mapping[raw] ?? ""} onValueChange={(v) => onMap(raw, v)}>
              <SelectTrigger className="h-8 w-56">
                <SelectValue placeholder="Map to…" />
              </SelectTrigger>
              <SelectContent>
                {options.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

`frontend/src/features/admin/import/PreviewTable.tsx`:

```tsx
import { AlertTriangle } from "lucide-react";
import type { ImportPreviewOut } from "@/lib/api/types";

export function PreviewTable({ preview }: { preview: ImportPreviewOut }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-4 text-sm">
        <Stat label="Rows" value={preview.total_rows} />
        <Stat label="Actions" value={preview.actions} />
        <Stat label="Notes" value={preview.notes} />
        <Stat label="Updates" value={preview.updates} />
      </div>

      {preview.errors.length > 0 && (
        <div className="rounded-md border border-danger/40 bg-danger/5 p-3 text-sm">
          <p className="mb-1 font-medium text-danger">Blocking errors</p>
          <ul className="list-inside list-disc text-fg-muted">
            {preview.errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}

      {preview.warnings.length > 0 && (
        <details className="rounded-md border border-warning/40 bg-warning/5 p-3 text-sm">
          <summary className="flex cursor-pointer items-center gap-2 font-medium text-warning">
            <AlertTriangle className="size-4" /> {preview.warnings.length} warnings
          </summary>
          <ul className="mt-2 list-inside list-disc text-fg-muted">
            {preview.warnings.map((w, i) => (
              <li key={i}>
                row {w.excel_row}
                {w.entry_no != null ? ` (entry ${w.entry_no})` : ""}: {w.message}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="max-h-72 overflow-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-surface">
            <tr className="border-b border-border text-left text-fg-muted">
              <th className="px-3 py-2 font-medium">Entry</th>
              <th className="px-3 py-2 font-medium">Title</th>
              <th className="px-3 py-2 font-medium">Group</th>
              <th className="px-3 py-2 font-medium">Owner</th>
              <th className="px-3 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((r) => (
              <tr key={r.excel_row} className="border-b border-border/60 last:border-0">
                <td className="px-3 py-1.5 tabular-nums">{r.entry_no ?? "—"}</td>
                <td className="px-3 py-1.5">{r.title}</td>
                <td className="px-3 py-1.5">{r.group ?? "—"}</td>
                <td className="px-3 py-1.5">{r.owner_org ?? "—"}</td>
                <td className="px-3 py-1.5">{r.status ?? (r.kind === "note" ? "Note" : "—")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <span className="rounded-md border border-border bg-surface px-3 py-1.5">
      <span className="text-fg-muted">{label}:</span>{" "}
      <span className="font-semibold tabular-nums">{value}</span>
    </span>
  );
}
```

- [ ] **Step 5: Write the import page**

`frontend/src/features/admin/import/ImportPage.tsx`:

```tsx
import { useState } from "react";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import type { ImportPreviewOut } from "@/lib/api/types";
import { OWNER_ORGS, STATUSES } from "@/lib/constants";
import { OWNER_LABELS, STATUS_LABELS } from "@/lib/labels";
import { useToast } from "@/lib/toast";
import { useVocab } from "@/features/items/useVocab";
import { PreviewTable } from "./PreviewTable";
import { UnmappedPicker, type FieldOption } from "./UnmappedPicker";
import { EMPTY_OVERRIDES, type Overrides, useCommit, usePreview } from "./useImport";

const OWNER_OPTS: FieldOption[] = OWNER_ORGS.map((v) => ({ value: v, label: OWNER_LABELS[v] }));
const STATUS_OPTS: FieldOption[] = STATUSES.map((v) => ({ value: v, label: STATUS_LABELS[v] }));

export function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [overrides, setOverrides] = useState<Overrides>(EMPTY_OVERRIDES);
  const [preview, setPreview] = useState<ImportPreviewOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const previewMut = usePreview();
  const commitMut = useCommit();
  const { toast } = useToast();
  const { groups, categories } = useVocab();

  const groupOpts: FieldOption[] = groups.map((g) => ({ value: g.value, label: g.value }));
  const categoryOpts: FieldOption[] = categories.map((c) => ({ value: c.value, label: c.value }));

  async function runPreview(nextFile: File, nextOverrides: Overrides) {
    setError(null);
    try {
      setPreview(await previewMut.mutateAsync({ file: nextFile, overrides: nextOverrides }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preview failed.");
    }
  }

  function onSelectFile(f: File | null) {
    setFile(f);
    setOverrides(EMPTY_OVERRIDES);
    setPreview(null);
    if (f) void runPreview(f, EMPTY_OVERRIDES);
  }

  function setMap(field: keyof Overrides, raw: string, target: string) {
    setOverrides((prev) => ({ ...prev, [field]: { ...prev[field], [raw]: target } }));
  }

  async function commit() {
    if (!file) return;
    setError(null);
    try {
      const result = await commitMut.mutateAsync({ file, overrides });
      toast({
        title: `Imported ${result.items_created} items, ${result.updates_created} updates`,
        variant: "success",
      });
      setFile(null);
      setPreview(null);
      setOverrides(EMPTY_OVERRIDES);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Import failed.");
    }
  }

  const unmapped = preview?.unmapped ?? {};

  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <h2 className="text-base font-semibold">Import spreadsheet</h2>
        <p className="mt-1 text-sm text-fg-muted">
          Upload the master track sheet. Review the preview, map any unmapped values, then commit.
          Commit is all-or-nothing and rejects rows whose entry numbers already exist.
        </p>
      </div>

      <label className="flex w-fit cursor-pointer items-center gap-2 rounded-md border border-border-strong px-4 py-2 text-sm font-medium hover:bg-surface-2">
        <Upload className="size-4" />
        {file ? file.name : "Choose .xlsx file"}
        <input
          type="file"
          accept=".xlsx"
          className="sr-only"
          aria-label="Spreadsheet file"
          onChange={(e) => onSelectFile(e.target.files?.[0] ?? null)}
        />
      </label>

      {previewMut.isPending && <p className="text-sm text-fg-muted">Analysing…</p>}
      {error && <p className="text-sm text-danger">{error}</p>}

      {preview && (
        <>
          <PreviewTable preview={preview} />

          {(unmapped.group?.length ||
            unmapped.category?.length ||
            unmapped.owner?.length ||
            unmapped.status?.length) && (
            <div className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-4">
              <p className="text-sm font-medium">Map unmapped values</p>
              <UnmappedPicker title="Group" rawValues={unmapped.group ?? []} options={groupOpts} mapping={overrides.group} onMap={(r, t) => setMap("group", r, t)} />
              <UnmappedPicker title="Category" rawValues={unmapped.category ?? []} options={categoryOpts} mapping={overrides.category} onMap={(r, t) => setMap("category", r, t)} />
              <UnmappedPicker title="Owner" rawValues={unmapped.owner ?? []} options={OWNER_OPTS} mapping={overrides.owner} onMap={(r, t) => setMap("owner", r, t)} />
              <UnmappedPicker title="Status" rawValues={unmapped.status ?? []} options={STATUS_OPTS} mapping={overrides.status} onMap={(r, t) => setMap("status", r, t)} />
              <Button
                variant="outline"
                size="sm"
                className="self-start"
                disabled={!file || previewMut.isPending}
                onClick={() => file && runPreview(file, overrides)}
              >
                Re-check with mappings
              </Button>
            </div>
          )}

          <Button disabled={!preview.committable || commitMut.isPending} onClick={commit}>
            {commitMut.isPending ? "Importing…" : "Commit import"}
          </Button>
          {!preview.committable && (
            <p className="text-sm text-fg-muted">
              Resolve the errors and unmapped values above, then re-check to enable commit.
            </p>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Write the export button and export page; wire the items toolbar**

`frontend/src/features/items/ExportButton.tsx`:

```tsx
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { downloadExport } from "@/lib/download";
import { filtersToSearchParams, type ItemFilters } from "./filters";

export function ExportButton({ filters }: { filters?: ItemFilters }) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={() => downloadExport(filters ? filtersToSearchParams(filters) : new URLSearchParams())}
    >
      <Download className="size-4" /> Export
    </Button>
  );
}
```

`frontend/src/features/admin/export/ExportPage.tsx`:

```tsx
import { ExportButton } from "@/features/items/ExportButton";

export function ExportPage() {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h2 className="text-base font-semibold">Export</h2>
      <p className="text-sm text-fg-muted">
        Download all current items as an Excel workbook in the original column layout (plus Last
        Updated and Updated By). To export a filtered subset, use the Export button on the Items
        table with filters applied.
      </p>
      <ExportButton />
    </div>
  );
}
```

In `frontend/src/features/items/ItemsPage.tsx`: import `ExportButton` and add `<ExportButton filters={filters} />` inside the `<FilterBar>` slot (after `<NewItemButton />`).

In `frontend/src/app/router.tsx`: import `ImportPage`, `ExportPage`; add under the admin children `<Route path="import" element={<ImportPage />} />` and `<Route path="export" element={<ExportPage />} />`.

- [ ] **Step 7: Write the failing import test (file upload + preview render; selects stay closed)**

`frontend/src/features/admin/import/ImportPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/lib/toast";
import { ImportPage } from "./ImportPage";

function preview() {
  return {
    file_name: "sheet.xlsx",
    total_rows: 57,
    actions: 52,
    notes: 5,
    updates: 37,
    unmapped: { group: [], category: [], owner: ["formulation"], status: [] },
    errors: [],
    warnings: [{ excel_row: 3, entry_no: 2, message: "status blank, defaulted to open" }],
    committable: false,
    rows: [
      {
        excel_row: 2, entry_no: 1, kind: "action", title: "Confirm EP compliance",
        group: "General Issues", category: "QA", owner_org: "gensci", status: "open",
        priority: "p1", raised_on: "2026-02-05", due_on: null, updates: 0, warnings: [],
      },
    ],
  };
}

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = { success: true, data: [], error: null, meta: null };
    if (url.includes("/import/excel/preview")) body = { success: true, data: preview(), error: null, meta: null };
    else if (url.includes("/vocab")) body = { success: true, data: [], error: null, meta: null };
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
}

afterEach(() => vi.restoreAllMocks());

test("previews an uploaded file and surfaces counts and unmapped values", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ImportPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
  const input = screen.getByLabelText(/spreadsheet file/i);
  await userEvent.upload(input, new File(["x"], "sheet.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  expect(await screen.findByText("57")).toBeInTheDocument(); // total rows stat
  expect(await screen.findByText(/map unmapped values/i)).toBeInTheDocument();
  expect(screen.getByText("formulation")).toBeInTheDocument(); // unmapped owner value
});
```

- [ ] **Step 8: Run the test and build**

Run: `cd frontend && npx vitest run src/features/admin/import`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/api/client.ts frontend/src/lib/api/types.ts frontend/src/lib/download.ts \
  frontend/src/features/admin/import frontend/src/features/admin/export \
  frontend/src/features/items/ExportButton.tsx frontend/src/features/items/ItemsPage.tsx \
  frontend/src/app/router.tsx
git commit -m "feat(frontend): add Excel import (preview/commit) and export"
# append your session's Co-Authored-By trailer
```

---

### Task 6: Final gates, checklist, and dev log

**Files:**
- Modify: `docs/superpowers/implementation-checklist.md` (tick Phase 3)
- Create: `docs/superpowers/logs/2026-09-07-phase3-dev-log.md`

- [ ] **Step 1: Run every frontend gate**

Run: `cd frontend && npm run typecheck` → no errors.
Run: `cd frontend && npm test` → all suites pass (Phase 2's 28 plus the new dashboard, board (columns + move), users, vocab, and import suites).
Run: `cd frontend && npm run lint` → ESLint + Prettier clean (fix with `npm run format` and targeted edits; react-refresh warnings on provider+hook files are acceptable).
Run: `cd frontend && npm run build` → succeeds.

- [ ] **Step 2: Sanity-check against a running backend (optional but recommended)**

With the backend running (`cd backend && uv run --python 3.13.12 uvicorn app.main:app`) and `npm run dev`, log in as an admin and click through: dashboard tiles link into filtered items; board drag moves a card and it sticks after refresh; invite creates a copyable link; a vocab rename reflects on items; import preview shows counts; export downloads an xlsx. (The drag and dialogs are the parts unit tests can't cover — this is where they're verified before Playwright in Phase 4.)

- [ ] **Step 3: Update the implementation checklist**

In `docs/superpowers/implementation-checklist.md`, under the Phase 3 section, add the plan link and tick:

```markdown
## Phase 3 — Board, dashboard, admin (own plan required)

**Plan:** `docs/superpowers/plans/2026-09-07-phase3-board-dashboard-admin.md`. **Dev log:** `docs/superpowers/logs/2026-09-07-phase3-dev-log.md`.

- [x] Dashboard: stat tiles, needs-attention, activity feed (org filter, load more), breakdowns.
- [x] Kanban board: columns per status, collapse completed/cancelled, drag-to-change-status (optimistic + rollback), Table/Board toggle persisted.
- [x] Admin — users & invitations: list, change role/org/active, reset link, invite (copyable link), revoke.
- [x] Admin — vocabularies: add, rename, reorder, deactivate; pickers show active only.
- [x] Admin — import (preview → map unmapped → commit) and export (filtered + all).
- [x] Frontend tests (Vitest): dashboard from mocked summary, board grouping + optimistic move, admin screens.
```

- [ ] **Step 4: Write the Phase 3 dev log**

`docs/superpowers/logs/2026-09-07-phase3-dev-log.md` — record: the dnd-kit choice and why the board move is unit-tested at the hook level (Radix/dnd overlays hang jsdom, per Phase 2); the invitation-link limitation (raw token only available at create time; pending rows show Revoke only); the vocab picker active-only fix; and the final test/lint/build counts. Follow the Phase 2 dev-log format (only deviations and fixes, not routine steps).

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/implementation-checklist.md docs/superpowers/logs/2026-09-07-phase3-dev-log.md
git commit -m "docs: record Phase 3 completion and dev log"
# append your session's Co-Authored-By trailer
```

- [ ] **Step 6: Push (updates PR #2, or open a fresh PR per branch policy)**

```bash
git push -u origin claude/phase-2-frontend-plan-p8h3e5
```

Retry with exponential backoff only on network errors. Do not open a new PR unless the branch policy requires it (e.g. PR #2 already merged).

---

## Self-review

**1. Spec coverage (§10 board/dashboard/admin, §9 import/export, §8 vocab, §6 permissions).**

| Spec requirement | Task |
|---|---|
| Table/Board toggle persisted per browser | 2 (`ViewToggle`, `localStorage`) |
| Board: one column per status, notes excluded | 2 (`kind=action`, `BOARD_STATUSES`) |
| Board: completed/cancelled start collapsed | 2 (`board-prefs` default) |
| Board: cards show entry no, title, priority, owner, due, stale | 2 (`BoardCard`; stale marker = overdue/`DueDate`) |
| Board: drag → PATCH status, optimistic + rollback | 2 (`useMoveItemStatus`) |
| Board: cards order by priority then due | 2 (`orderCards`) |
| Dashboard default after login | 1 (index + login target → `/dashboard`) |
| Dashboard: tiles, needs-attention, activity (org filter, load more), breakdowns | 1 |
| Admin: users & invitations (invite → copyable link, revoke) | 3 |
| Admin: vocab (add/rename/reorder/deactivate) | 4 |
| Admin: import preview → unmapped pickers → commit | 5 |
| Export xlsx (filtered + all), any user | 5 (`ExportButton` on items + admin) |
| Admin-only gating (not UI-only) | 3 (`AdminRoute`; backend enforces) |
| Frontend tests: table filters, board drag status, item form, dashboard from mocked summary | Phase 2 (filters/form) + Task 1 (dashboard) + Task 2 (move hook) |

Deferred to Phase 4 (correctly): Playwright e2e (incl. the real drag gesture), CI, Postgres/proxy profiles, deployment note.

**2. Placeholder scan.** The only deliberately-flagged placeholder is the pending-invitation copy link in Task 3 Step 5, with an explicit **Recommended: implement option (a)** (remove it) — not left ambiguous. No "add error handling"/"TODO" steps; every code step is complete.

**3. Type/naming consistency.** New query keys (`users.admin`, `invitations.list`) are added once in `query.ts` and used consistently. `Overrides` shape matches the backend `ImportOverrides` fields (`group`/`category`/`owner`/`status`). `useMoveItemStatus` updates the same `["items","list"]` caches the table/board read. `ViewToggle` persistence key (`cmc-items-view`) and board collapse key (`cmc-board-collapsed`) don't collide with Phase 2's `cmc-item-columns`/`cmc-theme`.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-07-phase3-board-dashboard-admin.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks. REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
**2. Inline Execution** — execute in this session with checkpoints. REQUIRED SUB-SKILL: superpowers:executing-plans.

**Which approach?**

