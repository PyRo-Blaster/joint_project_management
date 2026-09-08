# Phase 3 Development Log

Branch: `claude/phase-2-frontend-plan-p8h3e5` (PR #2; consolidated with Phase 4). Started 2026-09-08.
Records notable decisions, deviations, and fixes during Phase 3 (board, dashboard, admin).
Routine "wrote file → tests passed → committed" steps are not logged.

## Environment
- Same as Phase 2: node v22.22.2, backend tests on Python 3.13.12. Frontend baseline before
  starting: 28 tests green.

## Task-by-task notes

### Dashboard
- No surprises. `ActivityFeed` uses `useInfiniteQuery` against `/activity` (org filter + load more)
  rather than the summary's `recent_activity`, so filtering and paging are consistent. Made the
  dashboard the post-login default (index redirect + `LoginPage` fallback → `/dashboard`).

### Kanban board
- Added `@dnd-kit/core` + `sortable` + `utilities`. The optimistic status move
  (`useMoveItemStatus`) updates every cached `["items","list"]` entry on mutate and rolls back on
  error; both paths are unit-tested with `renderHook`. Board grouping/ordering is a pure function,
  also unit-tested. Per the plan, the **drag gesture itself is not tested in jsdom** (dnd overlays
  hang the event loop, same class of issue as Radix in Phase 2) — it's covered by the Phase 4
  Playwright golden path. `ViewToggle` navigates between `/items` and `/board` and persists the
  choice.

### Admin — users & invitations
- **Fix:** `ROLES`/`Role` were never added to `src/lib/constants.ts` in Phase 2, so `UserRow`,
  `InviteDialog`, and `useUsersAdmin` failed typecheck (and the users test crashed at runtime on
  `ROLES.map`). Added `ROLES = ["admin","member"]` and the `Role` type. Added `users.admin` and
  `invitations.list` query keys and `InvitationCreatedOut`/`ResetLinkOut` aliases.
- **Deviation (invitation link):** `GET /invitations` returns metadata but not the raw token (it's
  hashed at rest), so a pending-invitation row cannot reconstruct the accept URL. Implemented the
  plan's recommended option (a): pending rows show **Revoke only**; the one-time link is shown once,
  at creation, in the InviteDialog. Sidebar hides the Admin entry for non-admins (route also guarded
  by `AdminRoute`; backend enforces too).

### Admin — vocab
- Pickers (`useVocab`) now filter to `is_active` (spec §8); the admin screen fetches the same
  `qk.vocab.list()` cache but keeps inactive terms. Reorder swaps `sort_order` with the neighbour
  (two PATCHes). No surprises.

### Admin — import & export
- Added `apiUpload` (multipart, no JSON content-type) to the client for preview/commit. Import page:
  upload → preview (counts/warnings/rows) → per-field unmapped pickers → re-check → commit
  (all-or-nothing). Export is a cookie-authed GET via a transient anchor (`lib/download.ts`), on both
  the items toolbar (with current filters) and the admin Export tab (all items) — export is allowed
  for any authenticated user per §6.

## Phase 3 result
All screens complete. **36 frontend tests (22 files)** passing; `npm run typecheck` + `npm run build`
clean; ESLint 0 errors (6 non-fatal react-refresh warnings on provider+hook files) / Prettier clean.
Backend untouched in Phase 3 (still 100 tests on 3.13). The board drag gesture and Radix dialogs are
validated by the Phase 4 Playwright e2e rather than jsdom.
