# Phase 2: Frontend Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the frontend core of the joint CMC tracker — app shell, authentication, the items table, and the item detail view (fields, update timeline, history) — built into the same Docker image so that both GenSci and Yarrow can use the app from one container at `http://localhost:8000`.

**Architecture:** A Vite + React + TypeScript single-page app under `frontend/`, styled with Tailwind v4 using a CSS-variable design-token system for light/dark themes. Server state flows through TanStack Query over a thin, envelope-aware `fetch` client that always sends `X-Requested-With: fetch`, unwraps `{success, data, error, meta}`, and turns `success:false` into a typed `ApiError`. DTO types are generated from the backend's OpenAPI schema so the frontend never hand-copies field shapes. Forms use react-hook-form + zod schemas that mirror the backend pydantic models. In production the Vite build is emitted to `backend/static/` and served by FastAPI with an SPA fallback; in development Vite (`:5173`) proxies `/api` to FastAPI (`:8000`).

**Tech Stack:** Node ≥ 26, Vite 6, React 19, TypeScript 5.7, Tailwind CSS v4 (`@tailwindcss/vite`), TanStack Query v5, react-router-dom v7 (v6-compatible declarative API), react-hook-form v7 + zod v3, Radix UI primitives, class-variance-authority + clsx + tailwind-merge, lucide-react icons, openapi-typescript v7, Vitest v3 + Testing Library + MSW v2.

**Spec:** `docs/superpowers/specs/2026-09-06-joint-cmc-tracker-design.md` (§10 Frontend, §7 API, §11 error handling). **Phase 1 plan:** `docs/superpowers/plans/2026-09-06-phase1-backend-core.md` (the API this frontend consumes).

**Scope (this plan = Phase 2 only).** In scope: scaffold, design system, UI primitives, generated API layer, TanStack Query, app shell + routing, login, accept-invite/reset, session-expiry redirect, global error boundary, items table (sort, filter bar, search, column visibility, URL-synced filters), item create, item detail (side sheet + deep-link route, editable fields, update timeline, history diffs), Docker Node build stage + SPA fallback. **Deferred to Phase 3:** Kanban board, dashboard screen, admin screens (users/invites/vocab), import/export UI, and the full Vitest suite for those screens. This plan sets up the test infrastructure and writes tests for the logic it introduces; it does not build Phase 3 screens.

**Note on the `frontend-design` skill.** The spec (§10) says implementation "will follow the `frontend-design` skill". That skill is not available in this environment, and the org catalog's `design` plugin is design-workflow tooling (Figma handoff, critique, accessibility audits), not a React/Tailwind code generator. The aesthetic direction is therefore encoded directly in **Task 2 (Design system)** and applied through the primitives in **Task 3**: neutral surfaces, a single accent, semantic status/priority color, strong type hierarchy, generous table row height, and first-class light/dark — exactly the constraints §10 fixes. If the skill becomes available later, run it against Task 2 before building screens.

---

## Conventions for every task

- Repository root is the git repo root (`/home/user/joint_project_management` in this environment). Frontend commands run from `frontend/`: `cd frontend && npm run …`. Backend commands run from `backend/`. Commits run from the repo root.
- **Develop on branch `claude/phase-2-frontend-plan-p8h3e5`.** Never push to another branch without explicit permission.
- **Commit trailer:** end every commit with the co-authorship trailer your session requires. Do not embed a model version string in any committed file. The example `git commit` blocks below show the subject/body only; append your trailer.
- **Cadence per task (matches Phase 1):** write the failing test (RED) → run it and confirm it fails → write the minimal code (GREEN) → run the stated command → commit. One commit per task unless a task says otherwise.
- **TDD where it pays.** Logic (envelope client, filter⇄URL serialization, zod schemas, formatting) gets a real failing unit test first. Presentational primitives get a render/smoke test. Never skip the "confirm it fails" step.
- **Types come from the backend.** Never hand-retype a DTO. Import from the generated `src/lib/api/schema.d.ts` via the aliases in `src/lib/api/types.ts`. Only the response *envelope* and query/filter shapes are hand-written.
- **Enum labels come from one place.** `src/lib/labels.ts` mirrors `backend/app/constants.py` (`STATUS_LABELS`, `OWNER_LABELS`, `PRIORITY_LABELS`). Never inline a human label in a component.
- **Immutability & file size.** Immutable state updates only. Target 150–300 lines per file, 400 max; split by feature under `src/features/`, shared pieces under `src/components/` and `src/lib/`.
- **Every mutation sends `X-Requested-With: fetch`.** The shared client does this; never call `fetch` directly from a component.
- **Accessibility is not optional.** Every interactive control is keyboard-reachable and labelled; Radix primitives provide the focus management — use them rather than re-implementing dialogs/menus.

## File structure

```
frontend/
├── package.json                     # deps, scripts (dev, build, test, lint, gen:api)
├── tsconfig.json  tsconfig.node.json
├── vite.config.ts                   # React + Tailwind plugins, /api dev proxy, vitest config
├── index.html                       # #root, title, theme bootstrap script (no-flash)
├── .eslintrc.cjs  .prettierrc  .gitignore
├── openapi.json                     # snapshot dumped from the backend app (input to gen:api)
├── src/
│   ├── main.tsx                     # ReactDOM root, providers, router
│   ├── vite-env.d.ts
│   ├── app/
│   │   ├── router.tsx               # route table
│   │   ├── providers.tsx            # QueryClientProvider, ThemeProvider, ToastProvider
│   │   ├── layout/AppLayout.tsx     # topbar + sidebar shell, <Outlet/>
│   │   ├── layout/Sidebar.tsx  layout/Topbar.tsx  layout/UserMenu.tsx
│   │   ├── ProtectedRoute.tsx       # redirects to /login when unauthenticated
│   │   ├── ErrorBoundary.tsx        # global React error boundary
│   │   └── NotFound.tsx
│   ├── components/
│   │   ├── ui/                      # button, input, select, checkbox, badge, card,
│   │   │                            #   sheet, dialog, dropdown-menu, popover, tabs,
│   │   │                            #   toast, tooltip, skeleton, spinner, empty-state
│   │   └── domain/                  # StatusBadge, PriorityBadge, OwnerBadge, KindBadge,
│   │                                #   DueDate, RelativeTime, OrgAvatar, DiffTable
│   ├── features/
│   │   ├── auth/                    # LoginPage, AcceptInvitePage, useAuth, auth-schema
│   │   ├── items/                   # ItemsPage, ItemsTable, FilterBar, ColumnChooser,
│   │   │                            #   ItemForm, item-schema, useItems, useVocab, useUsers,
│   │   │                            #   filters (URL⇄state), columns
│   │   └── item-detail/            # ItemDetail(sheet+route), DetailFields, UpdatesTab,
│   │                                #   HistoryTab, useItem, useItemUpdates, useItemHistory
│   ├── lib/
│   │   ├── api/client.ts            # apiFetch/apiList, ApiError, X-Requested-With, 401 event
│   │   ├── api/schema.d.ts          # GENERATED by openapi-typescript (do not edit)
│   │   ├── api/types.ts             # DTO aliases from schema.d.ts + Envelope/Meta
│   │   ├── query.ts                 # queryClient, query-key factory `qk`
│   │   ├── labels.ts  constants.ts  # mirror backend constants
│   │   ├── format.ts                # dates, relative time, overdue/stale helpers
│   │   ├── theme.tsx                # ThemeProvider + useTheme (light/dark/system)
│   │   └── cn.ts                    # clsx + tailwind-merge
│   └── styles/globals.css           # @import tailwind; @theme tokens; base layer
├── test/
│   ├── setup.ts                     # jsdom, jest-dom, MSW server lifecycle
│   ├── msw/handlers.ts  msw/server.ts
│   └── utils.tsx                    # renderWithProviders
Repo root changes: Dockerfile (+frontend-build stage), backend/app/main.py (SPA fallback),
  docs/superpowers/implementation-checklist.md, docs/superpowers/logs/2026-09-06-phase2-dev-log.md
```

---

### Task 1: Frontend scaffold, dev proxy, and test harness

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/vite.config.ts`, `frontend/index.html`, `frontend/.gitignore`, `frontend/.prettierrc`, `frontend/.eslintrc.cjs`
- Create: `frontend/src/main.tsx`, `frontend/src/vite-env.d.ts`, `frontend/src/App.tsx` (temporary placeholder, replaced in Task 6)
- Create: `frontend/src/styles/globals.css` (minimal now; Task 2 fills tokens)
- Create: `frontend/test/setup.ts`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Create the Vite project files**

`frontend/package.json`:

```json
{
  "name": "cmc-tracker-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint . && prettier --check .",
    "format": "prettier --write .",
    "typecheck": "tsc -b --noEmit",
    "gen:api": "openapi-typescript ./openapi.json -o src/lib/api/schema.d.ts"
  },
  "dependencies": {
    "@radix-ui/react-checkbox": "^1.1.3",
    "@radix-ui/react-dialog": "^1.1.4",
    "@radix-ui/react-dropdown-menu": "^2.1.4",
    "@radix-ui/react-label": "^2.1.1",
    "@radix-ui/react-popover": "^1.1.4",
    "@radix-ui/react-select": "^2.1.4",
    "@radix-ui/react-tabs": "^1.1.2",
    "@radix-ui/react-toast": "^1.2.4",
    "@radix-ui/react-tooltip": "^1.1.6",
    "@tanstack/react-query": "^5.62.0",
    "class-variance-authority": "^0.7.1",
    "clsx": "^2.1.1",
    "lucide-react": "^0.469.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-hook-form": "^7.54.0",
    "react-router-dom": "^7.1.0",
    "tailwind-merge": "^2.6.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.0.0",
    "@testing-library/dom": "^10.4.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@typescript-eslint/eslint-plugin": "^8.19.0",
    "@typescript-eslint/parser": "^8.19.0",
    "@vitejs/plugin-react": "^4.3.4",
    "eslint": "^9.17.0",
    "eslint-plugin-react-hooks": "^5.1.0",
    "eslint-plugin-react-refresh": "^0.4.16",
    "jsdom": "^25.0.1",
    "msw": "^2.7.0",
    "openapi-typescript": "^7.5.0",
    "prettier": "^3.4.2",
    "tailwindcss": "^4.0.0",
    "typescript": "^5.7.2",
    "vite": "^6.0.5",
    "vitest": "^3.0.0"
  }
}
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": { "@/*": ["src/*"] },
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "test"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`frontend/tsconfig.node.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "noEmit": true
  },
  "include": ["vite.config.ts"]
}
```

`frontend/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Emitted here so the Docker runtime can serve it from /app/static.
    outDir: "dist",
    emptyOutDir: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./test/setup.ts"],
    css: true,
  },
});
```

`frontend/index.html` (the inline script sets the theme class before paint to avoid a flash):

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Joint CMC Tracker</title>
    <script>
      (function () {
        try {
          var t = localStorage.getItem("cmc-theme");
          var dark = t === "dark" || (!t && matchMedia("(prefers-color-scheme: dark)").matches);
          if (dark) document.documentElement.classList.add("dark");
        } catch (e) {}
      })();
    </script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`frontend/.gitignore`:

```
node_modules
dist
*.local
.eslintcache
coverage
```

`frontend/.prettierrc`:

```json
{ "printWidth": 100, "semi": true, "singleQuote": false, "trailingComma": "all" }
```

`frontend/.eslintrc.cjs`:

```cjs
module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  extends: [
    "eslint:recommended",
    "plugin:@typescript-eslint/recommended",
    "plugin:react-hooks/recommended",
  ],
  parser: "@typescript-eslint/parser",
  parserOptions: { ecmaVersion: "latest", sourceType: "module" },
  plugins: ["react-refresh"],
  ignorePatterns: ["dist", "src/lib/api/schema.d.ts"],
  rules: {
    "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
    "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
  },
};
```

- [ ] **Step 2: Create the entry point, placeholder app, minimal styles, and test setup**

`frontend/src/vite-env.d.ts`:

```ts
/// <reference types="vite/client" />
```

`frontend/src/styles/globals.css` (Task 2 replaces the body with real tokens):

```css
@import "tailwindcss";

body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
```

`frontend/src/App.tsx` (temporary — Task 6 replaces this with the router):

```tsx
export default function App() {
  return <h1>Joint CMC Tracker</h1>;
}
```

`frontend/src/main.tsx`:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`frontend/test/setup.ts` (MSW lifecycle is added in Task 18; kept minimal here):

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Write the failing smoke test**

`frontend/src/App.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders the app title", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: /joint cmc tracker/i })).toBeInTheDocument();
});
```

- [ ] **Step 4: Install dependencies and run the test to verify it fails, then passes**

Run: `cd frontend && npm install`
Expected: dependencies install, `node_modules/` and `package-lock.json` created.

Run: `cd frontend && npm test`
Expected: PASS (`1 passed`). If it errors on a missing module instead, that is the RED signal that a dependency name or path is wrong — fix and re-run until `1 passed`.

- [ ] **Step 5: Verify the dev server and production build work**

Run: `cd frontend && npm run build`
Expected: `tsc -b` succeeds and `vite build` writes `dist/index.html` and `dist/assets/*`.

(Optional sanity check, needs the backend running on :8000) Run: `cd frontend && npm run dev` and open `http://localhost:5173` — the heading renders and `/api/health` is proxied. Stop the server with Ctrl-C.

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig*.json \
  frontend/vite.config.ts frontend/index.html frontend/.gitignore frontend/.prettierrc \
  frontend/.eslintrc.cjs frontend/src frontend/test
git commit -m "feat(frontend): scaffold Vite + React + TS + Tailwind with dev proxy and test harness"
# append your session's Co-Authored-By trailer
```

---

### Task 2: Design system — tokens, themes, and the visual foundation

This task encodes the §10 visual direction: neutral surfaces, one accent, semantic status/priority color, strong type hierarchy, first-class light/dark. Everything downstream reads these tokens; components never hard-code hex values.

**Files:**
- Modify: `frontend/src/styles/globals.css` (replace with the full token system)
- Create: `frontend/src/lib/cn.ts`
- Create: `frontend/src/lib/theme.tsx`
- Test: `frontend/src/lib/theme.test.tsx`

- [ ] **Step 1: Write the token stylesheet**

Replace `frontend/src/styles/globals.css` with:

```css
@import "tailwindcss";

/* Dark theme is opt-in via a `.dark` class on <html> (set pre-paint in index.html). */
@custom-variant dark (&:where(.dark, .dark *));

/*
  Design tokens. Light values on :root, dark overrides under .dark.
  Palette philosophy (spec §10): a near-neutral slate ground, a single indigo accent,
  and saturated hues reserved strictly for status/priority so color always means something.
*/
:root {
  --bg: oklch(0.99 0.002 250);           /* app background */
  --surface: oklch(1 0 0);               /* cards, sheets, table */
  --surface-2: oklch(0.975 0.003 250);   /* subtle raised / hover */
  --border: oklch(0.92 0.004 250);
  --border-strong: oklch(0.85 0.006 250);
  --fg: oklch(0.22 0.01 260);            /* primary text */
  --fg-muted: oklch(0.5 0.01 260);       /* secondary text */
  --fg-subtle: oklch(0.62 0.01 260);     /* tertiary / placeholders */

  --accent: oklch(0.55 0.19 275);        /* indigo — the one accent */
  --accent-fg: oklch(0.99 0 0);
  --accent-weak: oklch(0.95 0.03 275);
  --ring: oklch(0.55 0.19 275 / 0.55);

  /* Semantic — status */
  --status-open: oklch(0.6 0.02 260);
  --status-in_progress: oklch(0.58 0.15 250);
  --status-blocked: oklch(0.58 0.2 25);
  --status-on_hold: oklch(0.7 0.13 85);
  --status-completed: oklch(0.6 0.15 155);
  --status-cancelled: oklch(0.6 0.01 260);

  /* Semantic — priority */
  --priority-p1: oklch(0.58 0.2 25);
  --priority-p2: oklch(0.7 0.13 85);
  --priority-p3: oklch(0.6 0.02 260);

  /* Semantic — org */
  --org-gensci: oklch(0.55 0.15 250);
  --org-yarrow: oklch(0.55 0.15 155);

  /* Feedback */
  --danger: oklch(0.55 0.2 25);
  --danger-fg: oklch(0.99 0 0);
  --warning: oklch(0.7 0.13 85);
  --success: oklch(0.6 0.15 155);

  --radius: 0.625rem;
  --shadow-sm: 0 1px 2px oklch(0.2 0.02 260 / 0.06);
  --shadow-md: 0 4px 16px oklch(0.2 0.02 260 / 0.08);
}

.dark {
  --bg: oklch(0.18 0.01 260);
  --surface: oklch(0.22 0.012 260);
  --surface-2: oklch(0.26 0.014 260);
  --border: oklch(0.32 0.012 260);
  --border-strong: oklch(0.4 0.014 260);
  --fg: oklch(0.96 0.005 260);
  --fg-muted: oklch(0.74 0.01 260);
  --fg-subtle: oklch(0.6 0.01 260);

  --accent: oklch(0.68 0.16 275);
  --accent-fg: oklch(0.18 0.01 260);
  --accent-weak: oklch(0.3 0.06 275);
  --ring: oklch(0.68 0.16 275 / 0.6);

  --status-open: oklch(0.72 0.02 260);
  --status-in_progress: oklch(0.72 0.13 250);
  --status-blocked: oklch(0.7 0.17 25);
  --status-on_hold: oklch(0.78 0.12 85);
  --status-completed: oklch(0.72 0.14 155);
  --status-cancelled: oklch(0.66 0.01 260);

  --priority-p1: oklch(0.72 0.17 25);
  --priority-p2: oklch(0.78 0.12 85);
  --priority-p3: oklch(0.7 0.02 260);

  --org-gensci: oklch(0.7 0.13 250);
  --org-yarrow: oklch(0.7 0.13 155);

  --danger: oklch(0.7 0.17 25);
  --danger-fg: oklch(0.18 0.01 260);
  --warning: oklch(0.78 0.12 85);
  --success: oklch(0.72 0.14 155);

  --shadow-sm: 0 1px 2px oklch(0 0 0 / 0.3);
  --shadow-md: 0 6px 24px oklch(0 0 0 / 0.4);
}

/* Map tokens into Tailwind's theme so `bg-surface`, `text-fg-muted`, `border-border`,
   `text-accent`, `rounded-lg` etc. resolve to the variables above. */
@theme inline {
  --color-bg: var(--bg);
  --color-surface: var(--surface);
  --color-surface-2: var(--surface-2);
  --color-border: var(--border);
  --color-border-strong: var(--border-strong);
  --color-fg: var(--fg);
  --color-fg-muted: var(--fg-muted);
  --color-fg-subtle: var(--fg-subtle);
  --color-accent: var(--accent);
  --color-accent-fg: var(--accent-fg);
  --color-accent-weak: var(--accent-weak);
  --color-danger: var(--danger);
  --color-danger-fg: var(--danger-fg);
  --color-warning: var(--warning);
  --color-success: var(--success);
  --color-ring: var(--ring);

  --radius-lg: var(--radius);
  --radius-md: calc(var(--radius) - 0.25rem);
  --radius-sm: calc(var(--radius) - 0.375rem);

  --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-mono: ui-monospace, "SF Mono", "Cascadia Code", Menlo, monospace;
}

@layer base {
  * {
    border-color: var(--color-border);
  }
  html {
    color-scheme: light dark;
  }
  body {
    margin: 0;
    background: var(--color-bg);
    color: var(--color-fg);
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
  }
  h1, h2, h3, h4 {
    letter-spacing: -0.01em;
    font-weight: 600;
  }
  :focus-visible {
    outline: 2px solid var(--color-accent);
    outline-offset: 2px;
  }
}
```

- [ ] **Step 2: Write the `cn` utility**

`frontend/src/lib/cn.ts`:

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge conditional class names, letting later Tailwind utilities win over earlier ones. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 3: Write the failing theme test**

`frontend/src/lib/theme.test.tsx`:

```tsx
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, useTheme } from "./theme";

function Probe() {
  const { theme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <button onClick={() => setTheme("dark")}>dark</button>
    </div>
  );
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});

test("defaults to system and toggles the html class + persists", async () => {
  render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  );
  expect(screen.getByTestId("theme")).toHaveTextContent("system");
  await act(() => userEvent.click(screen.getByText("dark")));
  expect(screen.getByTestId("theme")).toHaveTextContent("dark");
  expect(document.documentElement.classList.contains("dark")).toBe(true);
  expect(localStorage.getItem("cmc-theme")).toBe("dark");
});
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/theme.test.tsx`
Expected: FAIL — cannot resolve `./theme`.

- [ ] **Step 5: Write the theme provider**

`frontend/src/lib/theme.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type Theme = "light" | "dark" | "system";
const STORAGE_KEY = "cmc-theme";

type ThemeContextValue = { theme: Theme; setTheme: (t: Theme) => void };
const ThemeContext = createContext<ThemeContextValue | null>(null);

function systemPrefersDark(): boolean {
  return typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(theme: Theme): void {
  const dark = theme === "dark" || (theme === "system" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", dark);
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as Theme) || "system";
    } catch {
      return "system";
    }
  });

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    try {
      if (next === "system") localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage may be unavailable */
    }
    applyTheme(next);
  }, []);

  useEffect(() => {
    applyTheme(theme);
    if (theme !== "system") return;
    const mq = matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyTheme("system");
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [theme]);

  const value = useMemo(() => ({ theme, setTheme }), [theme, setTheme]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/theme.test.tsx`
Expected: PASS (`1 passed`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/styles/globals.css frontend/src/lib/cn.ts frontend/src/lib/theme.tsx \
  frontend/src/lib/theme.test.tsx
git commit -m "feat(frontend): add design-token system, light/dark themes, and cn util"
# append your session's Co-Authored-By trailer
```

---

### Task 3: UI primitives and domain badges

Small, composable, token-driven primitives (shadcn-style) plus domain badges. These are the vocabulary every screen speaks in — building them once keeps the app visually consistent.

**Files:**
- Create: `frontend/src/lib/labels.ts`, `frontend/src/lib/constants.ts`, `frontend/src/lib/format.ts`
- Create in `frontend/src/components/ui/`: `button.tsx`, `input.tsx`, `textarea.tsx`, `label.tsx`, `select.tsx`, `checkbox.tsx`, `badge.tsx`, `card.tsx`, `sheet.tsx`, `dialog.tsx`, `dropdown-menu.tsx`, `popover.tsx`, `tabs.tsx`, `tooltip.tsx`, `skeleton.tsx`, `spinner.tsx`, `empty-state.tsx`
- Create in `frontend/src/components/domain/`: `StatusBadge.tsx`, `PriorityBadge.tsx`, `OwnerBadge.tsx`, `KindBadge.tsx`, `DueDate.tsx`, `RelativeTime.tsx`
- Test: `frontend/src/components/ui/button.test.tsx`, `frontend/src/components/domain/StatusBadge.test.tsx`, `frontend/src/lib/format.test.ts`

- [ ] **Step 1: Write constants, labels, and formatting helpers with a failing format test**

`frontend/src/lib/constants.ts` (mirrors `backend/app/constants.py`; keep in sync):

```ts
export const STATUSES = [
  "open",
  "in_progress",
  "blocked",
  "on_hold",
  "completed",
  "cancelled",
] as const;
export const CLOSED_STATUSES = ["completed", "cancelled"] as const;
export const PRIORITIES = ["p1", "p2", "p3"] as const;
export const OWNER_ORGS = ["gensci", "yarrow", "joint"] as const;
export const ORGS = ["gensci", "yarrow"] as const;
export const KINDS = ["action", "note"] as const;

export type Status = (typeof STATUSES)[number];
export type Priority = (typeof PRIORITIES)[number];
export type OwnerOrg = (typeof OWNER_ORGS)[number];
export type Org = (typeof ORGS)[number];
export type Kind = (typeof KINDS)[number];
```

`frontend/src/lib/labels.ts` (mirrors the `*_LABELS` dicts):

```ts
import type { Kind, OwnerOrg, Priority, Status } from "./constants";

export const STATUS_LABELS: Record<Status, string> = {
  open: "Open",
  in_progress: "In progress",
  blocked: "Blocked",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const OWNER_LABELS: Record<OwnerOrg, string> = {
  gensci: "GenSci",
  yarrow: "Yarrow",
  joint: "GenSci/Yarrow",
};

export const ORG_LABELS: Record<string, string> = { gensci: "GenSci", yarrow: "Yarrow" };
export const PRIORITY_LABELS: Record<Priority, string> = { p1: "P1", p2: "P2", p3: "P3" };
export const KIND_LABELS: Record<Kind, string> = { action: "Action", note: "Note" };

/** Human label for a nullable status, treating null as a note. */
export function statusLabel(status: string | null): string {
  if (!status) return "Note";
  return STATUS_LABELS[status as Status] ?? status;
}
```

`frontend/src/lib/format.ts`:

```ts
/** All dates from the API are ISO `YYYY-MM-DD` (date) or ISO datetime strings (UTC, naive). */

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const RELATIVE_STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31536000],
  ["month", 2592000],
  ["week", 604800],
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];

/** "3 days ago", "in 2 hours", "just now". `now` is injectable for tests. */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const then = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : `${iso}Z`);
  if (Number.isNaN(then.getTime())) return "—";
  const diffSeconds = Math.round((then.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(diffSeconds);
  if (abs < 45) return "just now";
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, secs] of RELATIVE_STEPS) {
    if (abs >= secs) return rtf.format(Math.round(diffSeconds / secs), unit);
  }
  return "just now";
}

/** A due date is overdue when it is strictly before today (date-only comparison). */
export function isOverdue(dueOn: string | null | undefined, today: Date = new Date()): boolean {
  if (!dueOn) return false;
  const due = new Date(`${dueOn}T00:00:00`);
  const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return due.getTime() < midnight.getTime();
}

/** Days until due (negative if past). null when there is no due date. */
export function daysUntil(dueOn: string | null | undefined, today: Date = new Date()): number | null {
  if (!dueOn) return null;
  const due = new Date(`${dueOn}T00:00:00`);
  const midnight = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due.getTime() - midnight.getTime()) / 86400000);
}
```

`frontend/src/lib/format.test.ts`:

```ts
import { daysUntil, isOverdue, relativeTime } from "./format";

const NOW = new Date("2026-09-06T12:00:00Z");

test("relativeTime renders past and present", () => {
  expect(relativeTime("2026-09-06T12:00:00", NOW)).toBe("just now");
  expect(relativeTime("2026-09-03T12:00:00", NOW)).toMatch(/3 days ago/);
});

test("isOverdue and daysUntil compare by calendar day", () => {
  const today = new Date("2026-09-06T09:00:00");
  expect(isOverdue("2026-09-05", today)).toBe(true);
  expect(isOverdue("2026-09-06", today)).toBe(false);
  expect(daysUntil("2026-09-09", today)).toBe(3);
  expect(daysUntil(null, today)).toBeNull();
});
```

Run: `cd frontend && npx vitest run src/lib/format.test.ts`
Expected: FAIL — cannot resolve `./format` (RED). After creating the file above, re-run: PASS (`2 passed`).

- [ ] **Step 2: Write the base primitives (button, input, textarea, label, badge, card, skeleton, spinner, empty-state)**

`frontend/src/components/ui/button.tsx`:

```tsx
import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-accent text-accent-fg hover:opacity-90 shadow-sm",
        secondary: "bg-surface-2 text-fg hover:bg-border/60 border border-border",
        ghost: "text-fg-muted hover:bg-surface-2 hover:text-fg",
        danger: "bg-danger text-danger-fg hover:opacity-90 shadow-sm",
        outline: "border border-border-strong bg-transparent text-fg hover:bg-surface-2",
      },
      size: {
        sm: "h-8 px-3",
        md: "h-9 px-4",
        lg: "h-10 px-5",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
export { buttonVariants };
```

`frontend/src/components/ui/input.tsx`:

```tsx
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "flex h-9 w-full rounded-md border border-border bg-surface px-3 py-1 text-sm text-fg shadow-sm transition-colors placeholder:text-fg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-danger",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";
```

`frontend/src/components/ui/textarea.tsx`:

```tsx
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex min-h-20 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-fg shadow-sm transition-colors placeholder:text-fg-subtle focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 aria-[invalid=true]:border-danger",
      className,
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
```

`frontend/src/components/ui/label.tsx`:

```tsx
import * as LabelPrimitive from "@radix-ui/react-label";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Label = forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("text-sm font-medium text-fg", className)}
    {...props}
  />
));
Label.displayName = "Label";
```

`frontend/src/components/ui/badge.tsx`:

```tsx
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        neutral: "border-border bg-surface-2 text-fg-muted",
        accent: "border-transparent bg-accent-weak text-accent",
        outline: "border-border-strong text-fg-muted",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
```

`frontend/src/components/ui/card.tsx`:

```tsx
import { cn } from "@/lib/cn";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-lg border border-border bg-surface shadow-sm", className)}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("flex flex-col gap-1 p-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold", className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pt-0", className)} {...props} />;
}
```

`frontend/src/components/ui/skeleton.tsx`:

```tsx
import { cn } from "@/lib/cn";

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("animate-pulse rounded-md bg-surface-2", className)} {...props} />;
}
```

`frontend/src/components/ui/spinner.tsx`:

```tsx
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin text-fg-muted", className)} aria-hidden />;
}
```

`frontend/src/components/ui/empty-state.tsx`:

```tsx
import type { LucideIcon } from "lucide-react";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-surface/50 p-12 text-center">
      <Icon className="size-8 text-fg-subtle" aria-hidden />
      <div>
        <p className="font-medium text-fg">{title}</p>
        {description && <p className="mt-1 text-sm text-fg-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}
```

- [ ] **Step 3: Write the Radix-backed overlays and controls (select, checkbox, sheet, dialog, dropdown-menu, popover, tabs, tooltip)**

`frontend/src/components/ui/select.tsx`:

```tsx
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Select = SelectPrimitive.Root;
export const SelectValue = SelectPrimitive.Value;

export const SelectTrigger = forwardRef<
  React.ElementRef<typeof SelectPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex h-9 w-full items-center justify-between rounded-md border border-border bg-surface px-3 text-sm text-fg shadow-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 data-[placeholder]:text-fg-subtle",
      className,
    )}
    {...props}
  >
    {children}
    <SelectPrimitive.Icon>
      <ChevronDown className="size-4 opacity-60" />
    </SelectPrimitive.Icon>
  </SelectPrimitive.Trigger>
));
SelectTrigger.displayName = "SelectTrigger";

export const SelectContent = forwardRef<
  React.ElementRef<typeof SelectPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Content>
>(({ className, children, position = "popper", ...props }, ref) => (
  <SelectPrimitive.Portal>
    <SelectPrimitive.Content
      ref={ref}
      position={position}
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-md border border-border bg-surface text-fg shadow-md",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.Viewport className="p-1">{children}</SelectPrimitive.Viewport>
    </SelectPrimitive.Content>
  </SelectPrimitive.Portal>
));
SelectContent.displayName = "SelectContent";

export const SelectItem = forwardRef<
  React.ElementRef<typeof SelectPrimitive.Item>,
  React.ComponentPropsWithoutRef<typeof SelectPrimitive.Item>
>(({ className, children, ...props }, ref) => (
  <SelectPrimitive.Item
    ref={ref}
    className={cn(
      "relative flex cursor-pointer select-none items-center rounded-sm py-1.5 pl-8 pr-3 text-sm outline-none focus:bg-surface-2 data-[disabled]:opacity-50",
      className,
    )}
    {...props}
  >
    <span className="absolute left-2 flex size-4 items-center justify-center">
      <SelectPrimitive.ItemIndicator>
        <Check className="size-4" />
      </SelectPrimitive.ItemIndicator>
    </span>
    <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
  </SelectPrimitive.Item>
));
SelectItem.displayName = "SelectItem";
```

`frontend/src/components/ui/checkbox.tsx`:

```tsx
import * as CheckboxPrimitive from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Checkbox = forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>(({ className, ...props }, ref) => (
  <CheckboxPrimitive.Root
    ref={ref}
    className={cn(
      "peer size-4 shrink-0 rounded border border-border-strong shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:border-accent data-[state=checked]:bg-accent data-[state=checked]:text-accent-fg",
      className,
    )}
    {...props}
  >
    <CheckboxPrimitive.Indicator className="flex items-center justify-center">
      <Check className="size-3.5" />
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = "Checkbox";
```

`frontend/src/components/ui/sheet.tsx` (right-side panel used by item detail):

```tsx
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

export const SheetContent = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & { widthClass?: string }
>(({ className, children, widthClass = "w-full max-w-xl", ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed inset-y-0 right-0 z-50 flex flex-col border-l border-border bg-surface shadow-md transition-transform data-[state=closed]:translate-x-full",
        widthClass,
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-md p-1 text-fg-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <X className="size-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";

export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-b border-border px-6 py-4", className)} {...props} />;
}
export const SheetTitle = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold", className)} {...props} />
));
SheetTitle.displayName = "SheetTitle";
export const SheetDescription = DialogPrimitive.Description;
```

`frontend/src/components/ui/dialog.tsx` (centered modal for create/confirm):

```tsx
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const DialogContent = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 flex max-h-[90vh] w-full max-w-lg -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden rounded-lg border border-border bg-surface shadow-md",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-md p-1 text-fg-muted hover:bg-surface-2">
        <X className="size-4" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = "DialogContent";

export function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border-b border-border px-6 py-4", className)} {...props} />;
}
export const DialogTitle = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn("text-lg font-semibold", className)} {...props} />
));
DialogTitle.displayName = "DialogTitle";
export const DialogDescription = DialogPrimitive.Description;
export function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex justify-end gap-2 border-t border-border px-6 py-4", className)}
      {...props}
    />
  );
}
```

`frontend/src/components/ui/dropdown-menu.tsx`:

```tsx
import * as Menu from "@radix-ui/react-dropdown-menu";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;

export const DropdownMenuContent = forwardRef<
  React.ElementRef<typeof Menu.Content>,
  React.ComponentPropsWithoutRef<typeof Menu.Content>
>(({ className, sideOffset = 6, ...props }, ref) => (
  <Menu.Portal>
    <Menu.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-44 overflow-hidden rounded-md border border-border bg-surface p-1 text-fg shadow-md",
        className,
      )}
      {...props}
    />
  </Menu.Portal>
));
DropdownMenuContent.displayName = "DropdownMenuContent";

export const DropdownMenuItem = forwardRef<
  React.ElementRef<typeof Menu.Item>,
  React.ComponentPropsWithoutRef<typeof Menu.Item>
>(({ className, ...props }, ref) => (
  <Menu.Item
    ref={ref}
    className={cn(
      "flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-surface-2 data-[disabled]:opacity-50",
      className,
    )}
    {...props}
  />
));
DropdownMenuItem.displayName = "DropdownMenuItem";

export const DropdownMenuCheckboxItem = forwardRef<
  React.ElementRef<typeof Menu.CheckboxItem>,
  React.ComponentPropsWithoutRef<typeof Menu.CheckboxItem>
>(({ className, children, ...props }, ref) => (
  <Menu.CheckboxItem
    ref={ref}
    className={cn(
      "flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none focus:bg-surface-2",
      className,
    )}
    {...props}
  >
    <Menu.ItemIndicator>✓</Menu.ItemIndicator>
    {children}
  </Menu.CheckboxItem>
));
DropdownMenuCheckboxItem.displayName = "DropdownMenuCheckboxItem";

export function DropdownMenuSeparator() {
  return <Menu.Separator className="my-1 h-px bg-border" />;
}
export function DropdownMenuLabel({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-2 py-1.5 text-xs font-medium text-fg-subtle", className)} {...props} />;
}
```

`frontend/src/components/ui/popover.tsx`:

```tsx
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Popover = PopoverPrimitive.Root;
export const PopoverTrigger = PopoverPrimitive.Trigger;

export const PopoverContent = forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content>
>(({ className, align = "start", sideOffset = 6, ...props }, ref) => (
  <PopoverPrimitive.Portal>
    <PopoverPrimitive.Content
      ref={ref}
      align={align}
      sideOffset={sideOffset}
      className={cn(
        "z-50 w-64 rounded-md border border-border bg-surface p-3 text-fg shadow-md outline-none",
        className,
      )}
      {...props}
    />
  </PopoverPrimitive.Portal>
));
PopoverContent.displayName = "PopoverContent";
```

`frontend/src/components/ui/tabs.tsx`:

```tsx
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const Tabs = TabsPrimitive.Root;

export const TabsList = forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex h-9 items-center gap-1 border-b border-border", className)}
    {...props}
  />
));
TabsList.displayName = "TabsList";

export const TabsTrigger = forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "-mb-px border-b-2 border-transparent px-3 py-1.5 text-sm font-medium text-fg-muted transition-colors hover:text-fg data-[state=active]:border-accent data-[state=active]:text-fg",
      className,
    )}
    {...props}
  />
));
TabsTrigger.displayName = "TabsTrigger";

export const TabsContent = TabsPrimitive.Content;
```

`frontend/src/components/ui/tooltip.tsx`:

```tsx
import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { forwardRef } from "react";
import { cn } from "@/lib/cn";

export const TooltipProvider = TooltipPrimitive.Provider;
export const Tooltip = TooltipPrimitive.Root;
export const TooltipTrigger = TooltipPrimitive.Trigger;

export const TooltipContent = forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Portal>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 rounded-md bg-fg px-2 py-1 text-xs text-bg shadow-md",
        className,
      )}
      {...props}
    />
  </TooltipPrimitive.Portal>
));
TooltipContent.displayName = "TooltipContent";
```

- [ ] **Step 4: Write the domain badges**

`frontend/src/components/domain/StatusBadge.tsx`:

```tsx
import { statusLabel } from "@/lib/labels";

/** A status dot + label whose color comes from the --status-* token. */
export function StatusBadge({ status }: { status: string | null }) {
  const key = status ?? "note";
  const color = status ? `var(--status-${status})` : "var(--fg-subtle)";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-fg" data-status={key}>
      <span
        className="size-2 rounded-full"
        style={{ backgroundColor: color }}
        aria-hidden
      />
      {statusLabel(status)}
    </span>
  );
}
```

`frontend/src/components/domain/PriorityBadge.tsx`:

```tsx
import { PRIORITY_LABELS } from "@/lib/labels";
import type { Priority } from "@/lib/constants";

export function PriorityBadge({ priority }: { priority: string | null }) {
  if (!priority) return <span className="text-fg-subtle">—</span>;
  const color = `var(--priority-${priority})`;
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-semibold"
      style={{ color, backgroundColor: `color-mix(in oklch, ${color} 14%, transparent)` }}
    >
      {PRIORITY_LABELS[priority as Priority] ?? priority}
    </span>
  );
}
```

`frontend/src/components/domain/OwnerBadge.tsx`:

```tsx
import { OWNER_LABELS } from "@/lib/labels";
import type { OwnerOrg } from "@/lib/constants";

export function OwnerBadge({ owner }: { owner: string }) {
  const label = OWNER_LABELS[owner as OwnerOrg] ?? owner;
  const dot = (org: "gensci" | "yarrow") => (
    <span className="size-2 rounded-full" style={{ backgroundColor: `var(--org-${org})` }} />
  );
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      {owner === "joint" ? (
        <span className="flex items-center -space-x-0.5">
          {dot("gensci")}
          {dot("yarrow")}
        </span>
      ) : (
        dot(owner as "gensci" | "yarrow")
      )}
      {label}
    </span>
  );
}
```

`frontend/src/components/domain/KindBadge.tsx`:

```tsx
import { Badge } from "@/components/ui/badge";
import { KIND_LABELS } from "@/lib/labels";
import type { Kind } from "@/lib/constants";

export function KindBadge({ kind }: { kind: string }) {
  return (
    <Badge variant={kind === "note" ? "outline" : "neutral"}>
      {KIND_LABELS[kind as Kind] ?? kind}
    </Badge>
  );
}
```

`frontend/src/components/domain/DueDate.tsx`:

```tsx
import { AlertTriangle } from "lucide-react";
import { daysUntil, formatDate, isOverdue } from "@/lib/format";
import { cn } from "@/lib/cn";

/** Due date with an overdue color + icon and a "due soon" amber when within `soonDays`. */
export function DueDate({ dueOn, soonDays = 14 }: { dueOn: string | null; soonDays?: number }) {
  if (!dueOn) return <span className="text-fg-subtle">—</span>;
  const overdue = isOverdue(dueOn);
  const remaining = daysUntil(dueOn);
  const soon = !overdue && remaining !== null && remaining <= soonDays;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-sm",
        overdue ? "font-medium text-danger" : soon ? "text-warning" : "text-fg-muted",
      )}
    >
      {overdue && <AlertTriangle className="size-3.5" aria-hidden />}
      {formatDate(dueOn)}
    </span>
  );
}
```

`frontend/src/components/domain/RelativeTime.tsx`:

```tsx
import { formatDate, relativeTime } from "@/lib/format";

export function RelativeTime({ iso }: { iso: string | null }) {
  if (!iso) return <span className="text-fg-subtle">—</span>;
  return (
    <time dateTime={iso} title={formatDate(iso)} className="text-fg-muted">
      {relativeTime(iso)}
    </time>
  );
}
```

- [ ] **Step 5: Write the failing primitive/domain tests**

`frontend/src/components/ui/button.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./button";

test("renders variant classes and fires onClick", async () => {
  const onClick = vi.fn();
  render(
    <Button variant="danger" onClick={onClick}>
      Delete
    </Button>,
  );
  const btn = screen.getByRole("button", { name: "Delete" });
  expect(btn.className).toMatch(/bg-danger/);
  await userEvent.click(btn);
  expect(onClick).toHaveBeenCalledOnce();
});
```

`frontend/src/components/domain/StatusBadge.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

test("labels a known status and treats null as a note", () => {
  const { rerender } = render(<StatusBadge status="in_progress" />);
  expect(screen.getByText("In progress")).toBeInTheDocument();
  rerender(<StatusBadge status={null} />);
  expect(screen.getByText("Note")).toBeInTheDocument();
});
```

- [ ] **Step 6: Run the tests to verify they fail, then pass**

Run: `cd frontend && npx vitest run src/components src/lib/format.test.ts`
Expected: after all files above exist, PASS (`button`, `StatusBadge`, `format` suites green).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/constants.ts frontend/src/lib/labels.ts frontend/src/lib/format.ts \
  frontend/src/lib/format.test.ts frontend/src/components
git commit -m "feat(frontend): add UI primitives, domain badges, and formatting helpers"
# append your session's Co-Authored-By trailer
```

---

### Task 4: Generated API types and the envelope-aware fetch client

**Files:**
- Create: `frontend/openapi.json` (snapshot dumped from the backend)
- Generate: `frontend/src/lib/api/schema.d.ts` (via `npm run gen:api`; never hand-edited)
- Create: `frontend/src/lib/api/types.ts`, `frontend/src/lib/api/client.ts`
- Test: `frontend/src/lib/api/client.test.ts`

- [ ] **Step 1: Dump the OpenAPI schema from the backend and generate types**

The backend produces the schema without a running server. Run from the repo root:

```bash
cd backend && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../frontend/openapi.json
cd ../frontend && npm run gen:api
```

Expected: `frontend/openapi.json` is written and `openapi-typescript` reports `🚀 ... wrote src/lib/api/schema.d.ts`. Confirm the file defines `components["schemas"]["ItemOut"]`, `"UserOut"`, `"UpdateOut"`, `"AuditEventOut"`, `"DashboardSummary"`, `"VocabTermOut"`, `"InvitationOut"`, `"ItemCreate"`, `"ItemPatch"`.

Commit `openapi.json` so the type generation is reproducible offline; regenerate both files whenever the backend DTOs change.

- [ ] **Step 2: Write the DTO aliases and the envelope types**

`frontend/src/lib/api/types.ts`:

```ts
import type { components } from "./schema";

type S = components["schemas"];

// DTOs — generated, always in sync with the backend pydantic models.
export type ItemOut = S["ItemOut"];
export type ItemBrief = S["ItemBrief"];
export type ItemCreate = S["ItemCreate"];
export type ItemPatch = S["ItemPatch"];
export type UserOut = S["UserOut"];
export type UpdateOut = S["UpdateOut"];
export type UpdateCreate = S["UpdateCreate"];
export type UpdatePatch = S["UpdatePatch"];
export type AuditEventOut = S["AuditEventOut"];
export type DashboardSummary = S["DashboardSummary"];
export type VocabTermOut = S["VocabTermOut"];
export type InvitationOut = S["InvitationOut"];

// Envelope — hand-written; the backend wraps every response in this shape.
export interface Meta {
  total: number;
  page: number;
  limit: number;
}
export interface ErrorBody {
  code: string;
  message: string;
  fields?: Record<string, string> | null;
  request_id?: string | null;
}
export interface Envelope<T> {
  success: boolean;
  data: T | null;
  error: ErrorBody | null;
  meta: Meta | null;
}
```

- [ ] **Step 3: Write the failing client test**

`frontend/src/lib/api/client.test.ts`:

```ts
import { ApiError, apiFetch, apiList, AUTH_EXPIRED_EVENT } from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => vi.restoreAllMocks());

test("apiFetch unwraps data and sends the CSRF header on mutations", async () => {
  const fetchMock = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(jsonResponse({ success: true, data: { id: 1 }, error: null, meta: null }));

  const data = await apiFetch<{ id: number }>("/items/1", { method: "PATCH", body: { title: "x" } });
  expect(data).toEqual({ id: 1 });

  const [, init] = fetchMock.mock.calls[0];
  const headers = new Headers(init?.headers);
  expect(headers.get("X-Requested-With")).toBe("fetch");
  expect(headers.get("Content-Type")).toBe("application/json");
  expect(init?.body).toBe(JSON.stringify({ title: "x" }));
});

test("apiFetch throws a typed ApiError on success:false", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse(
      {
        success: false,
        data: null,
        error: { code: "validation_error", message: "Invalid", fields: { title: "required" } },
        meta: null,
      },
      422,
    ),
  );
  await expect(apiFetch("/items", { method: "POST", body: {} })).rejects.toMatchObject({
    code: "validation_error",
    status: 422,
    fields: { title: "required" },
  });
});

test("a 401 dispatches the auth-expired event and throws", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse({ success: false, data: null, error: { code: "unauthenticated", message: "x" }, meta: null }, 401),
  );
  const onExpire = vi.fn();
  window.addEventListener(AUTH_EXPIRED_EVENT, onExpire);
  await expect(apiFetch("/auth/me")).rejects.toBeInstanceOf(ApiError);
  expect(onExpire).toHaveBeenCalledOnce();
  window.removeEventListener(AUTH_EXPIRED_EVENT, onExpire);
});

test("apiList returns data and meta together", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    jsonResponse({ success: true, data: [{ id: 1 }], error: null, meta: { total: 1, page: 1, limit: 50 } }),
  );
  const { data, meta } = await apiList<{ id: number }>("/items");
  expect(data).toHaveLength(1);
  expect(meta.total).toBe(1);
});
```

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/api/client.test.ts`
Expected: FAIL — cannot resolve `./client`.

- [ ] **Step 5: Write the client**

`frontend/src/lib/api/client.ts`:

```ts
import type { Envelope, ErrorBody, Meta } from "./types";

export const AUTH_EXPIRED_EVENT = "cmc:auth-expired";
const BASE = "/api";

/** Typed error carrying the backend envelope's error body plus the HTTP status. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly fields?: Record<string, string> | null;
  readonly requestId?: string | null;

  constructor(status: number, error: ErrorBody) {
    super(error.message);
    this.name = "ApiError";
    this.code = error.code;
    this.status = status;
    this.fields = error.fields;
    this.requestId = error.request_id;
  }
}

export interface ApiOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE" | "PUT";
  body?: unknown;
  /** Query params; arrays become repeated keys (matches FastAPI list query params). */
  params?: Record<string, string | number | boolean | Array<string | number> | null | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, params?: ApiOptions["params"]): string {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === null || value === undefined || value === "") continue;
      if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, String(v)));
      else url.searchParams.set(key, String(value));
    }
  }
  return url.pathname + url.search;
}

async function request<T>(path: string, options: ApiOptions): Promise<Envelope<T>> {
  const { method = "GET", body, params, signal } = options;
  const headers: Record<string, string> = { "X-Requested-With": "fetch" };
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const response = await fetch(buildUrl(path, params), {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  });

  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT));
  }

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
    throw new ApiError(
      response.status,
      envelope.error ?? { code: "error", message: "Request failed" },
    );
  }
  return envelope;
}

/** Unwraps `data`. Use for single-object and action endpoints. */
export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const envelope = await request<T>(path, options);
  return envelope.data as T;
}

/** Returns `{ data, meta }` for list endpoints that page. */
export async function apiList<T>(
  path: string,
  options: ApiOptions = {},
): Promise<{ data: T[]; meta: Meta }> {
  const envelope = await request<T[]>(path, options);
  return {
    data: (envelope.data ?? []) as T[],
    meta: envelope.meta ?? { total: 0, page: 1, limit: 0 },
  };
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/api/client.test.ts`
Expected: PASS (`4 passed`).

- [ ] **Step 7: Commit**

```bash
git add frontend/openapi.json frontend/src/lib/api
git commit -m "feat(frontend): generate DTO types from OpenAPI and add envelope-aware fetch client"
# append your session's Co-Authored-By trailer
```

---

### Task 5: TanStack Query client, query keys, and toast infrastructure

**Files:**
- Create: `frontend/src/lib/query.ts`
- Create: `frontend/src/components/ui/toast.tsx`, `frontend/src/lib/toast.tsx`
- Test: `frontend/src/lib/query.test.ts`

- [ ] **Step 1: Write the failing query-key test**

`frontend/src/lib/query.test.ts`:

```ts
import { qk } from "./query";

test("query keys are stable and hierarchical", () => {
  expect(qk.items.list({ status: ["open"] })).toEqual(["items", "list", { status: ["open"] }]);
  expect(qk.items.detail(7)).toEqual(["items", "detail", 7]);
  expect(qk.items.updates(7)).toEqual(["items", 7, "updates"]);
  expect(qk.items.history(7)).toEqual(["items", 7, "history"]);
  expect(qk.auth.me()).toEqual(["auth", "me"]);
  expect(qk.vocab.list()).toEqual(["vocab"]);
  expect(qk.users.list()).toEqual(["users"]);
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/query.test.ts`
Expected: FAIL — cannot resolve `./query`.

- [ ] **Step 3: Write the query client and key factory**

`frontend/src/lib/query.ts`:

```ts
import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api/client";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error) => {
        // Never retry auth/permission/validation failures; retry transient ones once.
        if (error instanceof ApiError && error.status < 500) return false;
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

/** Centralised query keys so invalidation is precise and typo-free. */
export const qk = {
  auth: { me: () => ["auth", "me"] as const },
  items: {
    all: () => ["items"] as const,
    list: (filters: unknown) => ["items", "list", filters] as const,
    detail: (id: number) => ["items", "detail", id] as const,
    updates: (id: number) => ["items", id, "updates"] as const,
    history: (id: number) => ["items", id, "history"] as const,
  },
  vocab: { list: () => ["vocab"] as const },
  users: { list: () => ["users"] as const },
  dashboard: { summary: () => ["dashboard", "summary"] as const },
  activity: { list: (filters: unknown) => ["activity", filters] as const },
};
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/query.test.ts`
Expected: PASS (`1 passed`).

- [ ] **Step 5: Write the toast primitive and hook**

`frontend/src/components/ui/toast.tsx`:

```tsx
import * as ToastPrimitive from "@radix-ui/react-toast";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

export const ToastViewport = () => (
  <ToastPrimitive.Viewport className="fixed bottom-0 right-0 z-[100] flex w-96 max-w-[100vw] flex-col gap-2 p-4 outline-none" />
);

export function ToastRoot({
  variant = "default",
  ...props
}: React.ComponentPropsWithoutRef<typeof ToastPrimitive.Root> & {
  variant?: "default" | "success" | "error";
}) {
  return (
    <ToastPrimitive.Root
      className={cn(
        "flex items-start gap-3 rounded-md border bg-surface p-4 shadow-md data-[state=closed]:animate-out data-[state=closed]:fade-out",
        variant === "error" && "border-danger/40",
        variant === "success" && "border-success/40",
        variant === "default" && "border-border",
      )}
      {...props}
    />
  );
}

export const ToastTitle = ({ className, ...props }: ToastPrimitive.ToastTitleProps) => (
  <ToastPrimitive.Title className={cn("text-sm font-medium text-fg", className)} {...props} />
);
export const ToastDescription = ({ className, ...props }: ToastPrimitive.ToastDescriptionProps) => (
  <ToastPrimitive.Description className={cn("text-sm text-fg-muted", className)} {...props} />
);
export const ToastClose = () => (
  <ToastPrimitive.Close className="ml-auto text-fg-subtle hover:text-fg" aria-label="Dismiss">
    <X className="size-4" />
  </ToastPrimitive.Close>
);
export const ToastProviderPrimitive = ToastPrimitive.Provider;
```

`frontend/src/lib/toast.tsx`:

```tsx
import { createContext, useCallback, useContext, useMemo, useState } from "react";
import {
  ToastClose,
  ToastDescription,
  ToastProviderPrimitive,
  ToastRoot,
  ToastTitle,
  ToastViewport,
} from "@/components/ui/toast";

type Variant = "default" | "success" | "error";
interface ToastItem {
  id: number;
  title: string;
  description?: string;
  variant: Variant;
}
interface ToastApi {
  toast: (t: { title: string; description?: string; variant?: Variant }) => void;
}

const ToastContext = createContext<ToastApi | null>(null);
let nextId = 1;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const toast = useCallback<ToastApi["toast"]>(({ title, description, variant = "default" }) => {
    const id = nextId++;
    setItems((prev) => [...prev, { id, title, description, variant }]);
  }, []);

  const remove = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const api = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={api}>
      <ToastProviderPrimitive swipeDirection="right" duration={5000}>
        {children}
        {items.map((t) => (
          <ToastRoot key={t.id} variant={t.variant} onOpenChange={(open) => !open && remove(t.id)}>
            <div className="flex flex-col gap-0.5">
              <ToastTitle>{t.title}</ToastTitle>
              {t.description && <ToastDescription>{t.description}</ToastDescription>}
            </div>
            <ToastClose />
          </ToastRoot>
        ))}
        <ToastViewport />
      </ToastProviderPrimitive>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/query.ts frontend/src/lib/query.test.ts \
  frontend/src/components/ui/toast.tsx frontend/src/lib/toast.tsx
git commit -m "feat(frontend): add TanStack Query client, query-key factory, and toasts"
# append your session's Co-Authored-By trailer
```

---

### Task 6: Auth — hooks, zod form resolver, login page, accept-invite page

**Files:**
- Create: `frontend/src/lib/form.ts` (minimal zod → react-hook-form resolver; avoids an extra dependency)
- Create: `frontend/src/features/auth/useAuth.ts`, `frontend/src/features/auth/auth-schema.ts`
- Create: `frontend/src/features/auth/LoginPage.tsx`, `frontend/src/features/auth/AcceptInvitePage.tsx`, `frontend/src/features/auth/AuthField.tsx`
- Test: `frontend/src/features/auth/auth-schema.test.ts`, `frontend/src/features/auth/LoginPage.test.tsx`

- [ ] **Step 1: Write the zod resolver and auth schemas with a failing schema test**

`frontend/src/lib/form.ts`:

```ts
import type { FieldError, FieldValues, Resolver } from "react-hook-form";
import type { ZodType } from "zod";

/** Adapt a zod schema to react-hook-form without pulling in @hookform/resolvers. */
export function zodResolver<T extends FieldValues>(schema: ZodType<T>): Resolver<T> {
  return async (values) => {
    const result = schema.safeParse(values);
    if (result.success) return { values: result.data, errors: {} };
    const errors: Record<string, FieldError> = {};
    for (const issue of result.error.issues) {
      const path = issue.path.join(".");
      if (path && !errors[path]) errors[path] = { type: issue.code, message: issue.message };
    }
    return { values: {} as T, errors: errors as never };
  };
}
```

`frontend/src/features/auth/auth-schema.ts`:

```ts
import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const acceptSchema = z
  .object({
    name: z.string().min(1, "Name is required").max(200),
    password: z.string().min(10, "Use at least 10 characters"),
    confirm: z.string().min(1, "Confirm your password"),
  })
  .refine((v) => v.password === v.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });
export type AcceptValues = z.infer<typeof acceptSchema>;
```

`frontend/src/features/auth/auth-schema.test.ts`:

```ts
import { acceptSchema, loginSchema } from "./auth-schema";

test("loginSchema rejects a bad email and empty password", () => {
  expect(loginSchema.safeParse({ email: "nope", password: "" }).success).toBe(false);
  expect(loginSchema.safeParse({ email: "a@b.co", password: "x" }).success).toBe(true);
});

test("acceptSchema enforces min length and matching confirmation", () => {
  expect(
    acceptSchema.safeParse({ name: "A", password: "short", confirm: "short" }).success,
  ).toBe(false);
  expect(
    acceptSchema.safeParse({ name: "A", password: "longenough1", confirm: "different" }).success,
  ).toBe(false);
  expect(
    acceptSchema.safeParse({ name: "A", password: "longenough1", confirm: "longenough1" }).success,
  ).toBe(true);
});
```

Run: `cd frontend && npx vitest run src/features/auth/auth-schema.test.ts` → RED then GREEN once the schema file exists.

- [ ] **Step 2: Write the auth hooks**

`frontend/src/features/auth/useAuth.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "@/lib/api/client";
import type { UserOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

/** The current user, or null when unauthenticated. 401 resolves to null (not an error state). */
export function useMe() {
  return useQuery({
    queryKey: qk.auth.me(),
    queryFn: async (): Promise<UserOut | null> => {
      try {
        return await apiFetch<UserOut>("/auth/me");
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) return null;
        throw error;
      }
    },
    staleTime: 5 * 60_000,
    retry: false,
  });
}

export function useAuth() {
  const { data, isLoading, isFetched } = useMe();
  return { user: data ?? null, isLoading, isAuthenticated: !!data, isFetched };
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      apiFetch<UserOut>("/auth/login", { method: "POST", body }),
    onSuccess: (user) => qc.setQueryData(qk.auth.me(), user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<null>("/auth/logout", { method: "POST" }),
    onSuccess: () => {
      qc.setQueryData(qk.auth.me(), null);
      qc.clear();
    },
  });
}

export function useAcceptInvite() {
  return useMutation({
    mutationFn: (body: { token: string; name: string; password: string }) =>
      apiFetch<null>("/auth/accept-invite", { method: "POST", body }),
  });
}
```

- [ ] **Step 3: Write a reusable labelled field and the login page**

`frontend/src/features/auth/AuthField.tsx`:

```tsx
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function AuthField({
  id,
  label,
  error,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { id: string; label: string; error?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} aria-invalid={!!error} aria-describedby={error ? `${id}-error` : undefined} {...props} />
      {error && (
        <p id={`${id}-error`} className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
```

`frontend/src/features/auth/LoginPage.tsx`:

```tsx
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { zodResolver } from "@/lib/form";
import { AuthField } from "./AuthField";
import { loginSchema, type LoginValues } from "./auth-schema";
import { useLogin } from "./useAuth";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useLogin();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values);
      const params = new URLSearchParams(window.location.search);
      navigate(params.get("returnTo") || "/items", { replace: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 429) {
        setError("root", { message: "Too many attempts. Wait a minute and try again." });
      } else if (error instanceof ApiError && error.status === 401) {
        setError("root", { message: "Incorrect email or password." });
      } else {
        setError("root", { message: "Sign-in failed. Try again." });
      }
    }
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Joint CMC Tracker</CardTitle>
          <p className="text-sm text-fg-muted">Sign in to continue</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <AuthField
              id="email"
              label="Email"
              type="email"
              autoComplete="username"
              autoFocus
              error={errors.email?.message}
              {...register("email")}
            />
            <AuthField
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              error={errors.password?.message}
              {...register("password")}
            />
            {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
```

- [ ] **Step 4: Write the accept-invite / reset page**

`frontend/src/features/auth/AcceptInvitePage.tsx`:

```tsx
import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api/client";
import { zodResolver } from "@/lib/form";
import { AuthField } from "./AuthField";
import { acceptSchema, type AcceptValues } from "./auth-schema";
import { useAcceptInvite } from "./useAuth";

export function AcceptInvitePage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const accept = useAcceptInvite();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<AcceptValues>({ resolver: zodResolver(acceptSchema) });

  if (!token) {
    return (
      <main className="flex min-h-screen items-center justify-center p-4">
        <Card className="w-full max-w-sm">
          <CardContent className="pt-6 text-sm text-fg-muted">
            This link is missing its token. Ask an administrator for a new invitation link.
          </CardContent>
        </Card>
      </main>
    );
  }

  const onSubmit = handleSubmit(async (values) => {
    try {
      await accept.mutateAsync({ token, name: values.name, password: values.password });
      navigate("/login?accepted=1", { replace: true });
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 422
          ? "This link is invalid or has expired. Ask for a new one."
          : "Could not complete setup. Try again.";
      setError("root", { message });
    }
  });

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Set up your account</CardTitle>
          <p className="text-sm text-fg-muted">Choose a name and password to finish.</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <AuthField id="name" label="Full name" autoFocus error={errors.name?.message} {...register("name")} />
            <AuthField
              id="password"
              label="Password"
              type="password"
              autoComplete="new-password"
              error={errors.password?.message}
              {...register("password")}
            />
            <AuthField
              id="confirm"
              label="Confirm password"
              type="password"
              autoComplete="new-password"
              error={errors.confirm?.message}
              {...register("confirm")}
            />
            {errors.root && <p className="text-sm text-danger">{errors.root.message}</p>}
            <Button type="submit" disabled={isSubmitting} className="mt-2">
              {isSubmitting ? "Saving…" : "Create account"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
```

- [ ] **Step 5: Write the failing login page test**

`frontend/src/features/auth/LoginPage.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { LoginPage } from "./LoginPage";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("shows validation errors before calling the API", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  renderPage();
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  expect(await screen.findByText(/email is required/i)).toBeInTheDocument();
  expect(fetchSpy).not.toHaveBeenCalled();
});

test("surfaces an incorrect-credentials message on 401", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({ success: false, data: null, error: { code: "unauthenticated", message: "no" }, meta: null }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    ),
  );
  renderPage();
  await userEvent.type(screen.getByLabelText(/email/i), "a@b.co");
  await userEvent.type(screen.getByLabelText(/password/i), "whatever");
  await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
  await waitFor(() => expect(screen.getByText(/incorrect email or password/i)).toBeInTheDocument());
});
```

- [ ] **Step 6: Run the auth tests to verify they pass**

Run: `cd frontend && npx vitest run src/features/auth`
Expected: PASS (schema + login page suites green).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/form.ts frontend/src/features/auth
git commit -m "feat(frontend): add auth hooks, zod resolver, login and accept-invite pages"
# append your session's Co-Authored-By trailer
```

---

### Task 7: App shell — providers, layout, routing, protected routes, error boundary

**Files:**
- Create: `frontend/src/app/providers.tsx`, `frontend/src/app/ErrorBoundary.tsx`, `frontend/src/app/NotFound.tsx`
- Create: `frontend/src/app/ProtectedRoute.tsx`, `frontend/src/app/useAuthExpiredRedirect.ts`
- Create: `frontend/src/app/layout/AppLayout.tsx`, `layout/Sidebar.tsx`, `layout/Topbar.tsx`, `layout/UserMenu.tsx`, `layout/ThemeToggle.tsx`
- Create: `frontend/src/app/router.tsx`
- Modify: `frontend/src/main.tsx` (mount providers + router), delete `frontend/src/App.tsx` and `frontend/src/App.test.tsx`
- Test: `frontend/src/app/ProtectedRoute.test.tsx`

- [ ] **Step 1: Write the providers, error boundary, and 404**

`frontend/src/app/providers.tsx`:

```tsx
import { QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { queryClient } from "@/lib/query";
import { ThemeProvider } from "@/lib/theme";
import { ToastProvider } from "@/lib/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <TooltipProvider delayDuration={200}>{children}</TooltipProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
```

`frontend/src/app/ErrorBoundary.tsx`:

```tsx
import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

interface State {
  error: Error | null;
}

/** Global boundary for render-time crashes. Network/domain errors are handled by React Query. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("Unhandled UI error", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-6 text-center">
        <h1 className="text-xl font-semibold">Something went wrong</h1>
        <p className="max-w-md text-sm text-fg-muted">
          The page hit an unexpected error. Reloading usually fixes it.
        </p>
        <Button onClick={() => window.location.reload()}>Reload</Button>
      </div>
    );
  }
}
```

`frontend/src/app/NotFound.tsx`:

```tsx
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";

export function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <p className="text-5xl font-semibold text-fg-subtle">404</p>
      <p className="text-fg-muted">That page does not exist.</p>
      <Button asChild={false}>
        <Link to="/items">Back to items</Link>
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Write the session-expiry redirect hook and the protected route**

`frontend/src/app/useAuthExpiredRedirect.ts`:

```ts
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AUTH_EXPIRED_EVENT } from "@/lib/api/client";
import { queryClient } from "@/lib/query";
import { qk } from "@/lib/query";

/** When any request 401s, drop the cached user and bounce to /login with a returnTo. */
export function useAuthExpiredRedirect() {
  const navigate = useNavigate();
  useEffect(() => {
    const onExpired = () => {
      queryClient.setQueryData(qk.auth.me(), null);
      const path = window.location.pathname + window.location.search;
      if (window.location.pathname.startsWith("/login")) return;
      navigate(`/login?returnTo=${encodeURIComponent(path)}`, { replace: true });
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, onExpired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, onExpired);
  }, [navigate]);
}
```

`frontend/src/app/ProtectedRoute.tsx`:

```tsx
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/features/auth/useAuth";

/** Gate for authenticated routes. While `/auth/me` resolves, show a spinner. */
export function ProtectedRoute() {
  const { isAuthenticated, isFetched } = useAuth();
  const location = useLocation();

  if (!isFetched) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="size-6" />
      </div>
    );
  }
  if (!isAuthenticated) {
    const returnTo = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?returnTo=${returnTo}`} replace />;
  }
  return <Outlet />;
}
```

- [ ] **Step 3: Write the layout (topbar, sidebar, user menu, theme toggle)**

`frontend/src/app/layout/ThemeToggle.tsx`:

```tsx
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { setTheme } = useTheme();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Change theme">
          <Sun className="size-4 dark:hidden" />
          <Moon className="hidden size-4 dark:block" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => setTheme("light")}>
          <Sun className="size-4" /> Light
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("dark")}>
          <Moon className="size-4" /> Dark
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setTheme("system")}>
          <Monitor className="size-4" /> System
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

`frontend/src/app/layout/UserMenu.tsx`:

```tsx
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ORG_LABELS } from "@/lib/labels";
import { useAuth, useLogout } from "@/features/auth/useAuth";

export function UserMenu() {
  const { user } = useAuth();
  const logout = useLogout();
  const navigate = useNavigate();
  if (!user) return null;
  const initials = user.name.slice(0, 2).toUpperCase();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="gap-2">
          <span className="flex size-7 items-center justify-center rounded-full bg-accent-weak text-xs font-semibold text-accent">
            {initials}
          </span>
          <span className="hidden sm:inline">{user.name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          {user.email}
          <span className="mt-0.5 block font-normal text-fg-muted">
            {ORG_LABELS[user.org] ?? user.org} · {user.role === "admin" ? "Admin" : "Member"}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onSelect={async () => {
            await logout.mutateAsync();
            navigate("/login", { replace: true });
          }}
        >
          <LogOut className="size-4" /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

`frontend/src/app/layout/Sidebar.tsx` (dashboard/board/admin links are placeholders now; the routes arrive in Phase 3):

```tsx
import { LayoutDashboard, ListChecks, Columns3, Settings } from "lucide-react";
import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/items", label: "Items", icon: ListChecks },
  { to: "/board", label: "Board", icon: Columns3 },
  { to: "/admin", label: "Admin", icon: Settings },
];

export function Sidebar() {
  return (
    <nav className="flex w-56 shrink-0 flex-col gap-1 border-r border-border bg-surface p-3">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive ? "bg-accent-weak text-accent" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
            )
          }
        >
          <Icon className="size-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
```

`frontend/src/app/layout/Topbar.tsx`:

```tsx
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

export function Topbar() {
  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-surface px-4">
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold tracking-tight">Joint CMC Tracker</span>
        <span className="rounded bg-surface-2 px-1.5 py-0.5 text-xs text-fg-muted">GS098</span>
      </div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <UserMenu />
      </div>
    </header>
  );
}
```

`frontend/src/app/layout/AppLayout.tsx`:

```tsx
import { Outlet } from "react-router-dom";
import { useAuthExpiredRedirect } from "@/app/useAuthExpiredRedirect";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

export function AppLayout() {
  useAuthExpiredRedirect();
  return (
    <div className="flex min-h-screen flex-col">
      <Topbar />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 overflow-x-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write the router with a temporary items placeholder**

`frontend/src/app/router.tsx` (the `/items` element is replaced by `ItemsPage` in Task 9; `/items/:id` route is added in Task 12):

```tsx
import { Navigate, Route, Routes } from "react-router-dom";
import { AcceptInvitePage } from "@/features/auth/AcceptInvitePage";
import { LoginPage } from "@/features/auth/LoginPage";
import { AppLayout } from "./layout/AppLayout";
import { NotFound } from "./NotFound";
import { ProtectedRoute } from "./ProtectedRoute";

// Temporary placeholders — replaced by real screens in later tasks / Phase 3.
function ItemsPlaceholder() {
  return <p className="text-fg-muted">Items table coming in the next task.</p>;
}
function ComingSoon({ title }: { title: string }) {
  return <p className="text-fg-muted">{title} arrives in Phase 3.</p>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/accept-invite" element={<AcceptInvitePage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/items" replace />} />
          <Route path="/items" element={<ItemsPlaceholder />} />
          <Route path="/dashboard" element={<ComingSoon title="Dashboard" />} />
          <Route path="/board" element={<ComingSoon title="Board" />} />
          <Route path="/admin" element={<ComingSoon title="Admin" />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
```

- [ ] **Step 5: Rewire the entry point**

Replace `frontend/src/main.tsx` with:

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AppRoutes } from "./app/router";
import { ErrorBoundary } from "./app/ErrorBoundary";
import { Providers } from "./app/providers";
import "./styles/globals.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Providers>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </Providers>
    </ErrorBoundary>
  </StrictMode>,
);
```

Delete the now-obsolete placeholder: `rm frontend/src/App.tsx frontend/src/App.test.tsx`.

- [ ] **Step 6: Write the failing protected-route test**

`frontend/src/app/ProtectedRoute.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";

function renderAt(status: number) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify(
        status === 200
          ? { success: true, data: { id: 1, name: "A", email: "a@b.co", org: "gensci", role: "member", is_active: true, last_login_at: null, created_at: "2026-01-01T00:00:00" }, error: null, meta: null }
          : { success: false, data: null, error: { code: "unauthenticated", message: "no" }, meta: null },
      ),
      { status, headers: { "Content-Type": "application/json" } },
    ),
  );
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/items"]}>
        <Routes>
          <Route path="/login" element={<p>Login screen</p>} />
          <Route element={<ProtectedRoute />}>
            <Route path="/items" element={<p>Secret items</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("renders the child when authenticated", async () => {
  renderAt(200);
  expect(await screen.findByText("Secret items")).toBeInTheDocument();
});

test("redirects to /login when unauthenticated", async () => {
  renderAt(401);
  await waitFor(() => expect(screen.getByText("Login screen")).toBeInTheDocument());
});
```

- [ ] **Step 7: Run tests and the build**

Run: `cd frontend && npx vitest run src/app`
Expected: PASS (both protected-route cases).

Run: `cd frontend && npm run build`
Expected: type-checks and builds cleanly (no reference to the deleted `App.tsx`).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/app frontend/src/main.tsx
git rm frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "feat(frontend): add app shell — providers, layout, routing, protected routes, error boundary"
# append your session's Co-Authored-By trailer
```

---

### Task 8: Backend enabler — authenticated user directory endpoint

**Why:** The items list returns `assignee_id` as an integer, and the filter bar + item form need to resolve and pick assignees. `GET /users` is admin-only (spec §7), so members could not render assignee names or use the assignee filter. This task adds a minimal read-only directory (`id`, `name`, `org`, `is_active`) readable by any authenticated user — consistent with §6 ("both orgs see and edit everything; the org tag is for attribution and filtering"). No writes, no audit, no new permissions.

**Files:**
- Modify: `backend/app/schemas/users.py` (add `UserBrief`)
- Modify: `backend/app/api/users.py` (add `GET /users/directory`)
- Test: `backend/tests/api/test_user_directory_api.py`
- Regenerate: `frontend/openapi.json`, `frontend/src/lib/api/schema.d.ts`

- [ ] **Step 1: Write the failing API test**

`backend/tests/api/test_user_directory_api.py`:

```python
"""Any authenticated user can read the user directory; anonymous users cannot."""


def test_member_can_list_directory(member_client, admin, member):
    response = member_client.get("/api/users/directory")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    by_id = {u["id"]: u for u in body["data"]}
    assert by_id[admin.id]["name"] == "Ada Admin"
    assert by_id[member.id]["org"] == "yarrow"
    # Brief must not leak sensitive fields.
    assert "email" not in body["data"][0]
    assert "role" not in body["data"][0]


def test_directory_requires_authentication(client):
    response = client.get("/api/users/directory")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
```

Run: `cd backend && uv run pytest tests/api/test_user_directory_api.py -v`
Expected: FAIL — 404 (route does not exist yet).

- [ ] **Step 2: Add the `UserBrief` schema**

Add to `backend/app/schemas/users.py` (after `UserOut`):

```python
class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    org: str
    is_active: bool
```

- [ ] **Step 3: Add the directory route**

In `backend/app/api/users.py`, add `UserBrief` to the schema import and add the route **before** the `/{user_id}` routes:

```python
from app.api.deps import AdminUser, CurrentUser, DbDep, SettingsDep
from app.schemas.users import ResetLinkOut, UserBrief, UserOut, UserPatch


@router.get("/directory", response_model=Envelope[list[UserBrief]])
def directory(_user: CurrentUser, db: DbDep):
    return ok([UserBrief.model_validate(user) for user in list_users(db)])
```

(`CurrentUser` is imported from `app.api.deps`; add it to the existing import line as shown.)

- [ ] **Step 4: Run the test to verify it passes and the suite is still green**

Run: `cd backend && uv run pytest tests/api/test_user_directory_api.py -v`
Expected: `2 passed`.

Run: `cd backend && uv run pytest`
Expected: all previous tests plus the 2 new ones pass (no regressions).

- [ ] **Step 5: Regenerate the frontend types**

Run from the repo root:

```bash
cd backend && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../frontend/openapi.json
cd ../frontend && npm run gen:api
```

Expected: `openapi.json` updated and `schema.d.ts` now contains `components["schemas"]["UserBrief"]`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/users.py backend/app/api/users.py \
  backend/tests/api/test_user_directory_api.py frontend/openapi.json frontend/src/lib/api/schema.d.ts
git commit -m "feat(backend): add authenticated user directory endpoint for assignee resolution"
# append your session's Co-Authored-By trailer
```

---

### Task 9: Items data layer — URL-synced filters, items/vocab/users hooks

**Files:**
- Modify: `frontend/src/lib/api/types.ts` (add `UserBrief` alias)
- Create: `frontend/src/features/items/filters.ts` (filter type + URL⇄state serialization)
- Create: `frontend/src/features/items/useItems.ts`, `useVocab.ts`, `useUsers.ts`
- Test: `frontend/src/features/items/filters.test.ts`

- [ ] **Step 1: Add the `UserBrief` alias**

Add to `frontend/src/lib/api/types.ts` (in the DTO section):

```ts
export type UserBrief = S["UserBrief"];
```

- [ ] **Step 2: Write the filter type + serialization with a failing test**

`frontend/src/features/items/filters.ts`:

```ts
import type { Kind, OwnerOrg, Priority, Status } from "@/lib/constants";

export interface ItemFilters {
  status: Status[];
  priority: Priority[];
  group: string[];
  category: string[];
  owner_org: OwnerOrg[];
  kind: Kind | null;
  assignee_id: number | null;
  due_before: string | null;
  due_after: string | null;
  q: string | null;
  sort: string;
  direction: "asc" | "desc";
  page: number;
  limit: number;
}

export const DEFAULT_FILTERS: ItemFilters = {
  status: [],
  priority: [],
  group: [],
  category: [],
  owner_org: [],
  kind: null,
  assignee_id: null,
  due_before: null,
  due_after: null,
  q: null,
  sort: "entry_no",
  direction: "asc",
  page: 1,
  limit: 50,
};

const ARRAY_KEYS = ["status", "priority", "group", "category", "owner_org"] as const;

/** Read filters out of URL search params, falling back to defaults. */
export function parseFilters(params: URLSearchParams): ItemFilters {
  const filters: ItemFilters = {
    ...DEFAULT_FILTERS,
    status: params.getAll("status") as Status[],
    priority: params.getAll("priority") as Priority[],
    group: params.getAll("group"),
    category: params.getAll("category"),
    owner_org: params.getAll("owner_org") as OwnerOrg[],
    kind: (params.get("kind") as Kind | null) || null,
    assignee_id: params.get("assignee_id") ? Number(params.get("assignee_id")) : null,
    due_before: params.get("due_before"),
    due_after: params.get("due_after"),
    q: params.get("q"),
    sort: params.get("sort") || DEFAULT_FILTERS.sort,
    direction: params.get("direction") === "desc" ? "desc" : "asc",
    page: params.get("page") ? Math.max(1, Number(params.get("page"))) : 1,
    limit: params.get("limit") ? Number(params.get("limit")) : DEFAULT_FILTERS.limit,
  };
  return filters;
}

/** Serialize filters to URL search params, omitting empties so links stay clean. */
export function filtersToSearchParams(filters: ItemFilters): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of ARRAY_KEYS) {
    for (const value of filters[key]) params.append(key, value);
  }
  if (filters.kind) params.set("kind", filters.kind);
  if (filters.assignee_id != null) params.set("assignee_id", String(filters.assignee_id));
  if (filters.due_before) params.set("due_before", filters.due_before);
  if (filters.due_after) params.set("due_after", filters.due_after);
  if (filters.q) params.set("q", filters.q);
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set("sort", filters.sort);
  if (filters.direction !== DEFAULT_FILTERS.direction) params.set("direction", filters.direction);
  if (filters.page !== 1) params.set("page", String(filters.page));
  if (filters.limit !== DEFAULT_FILTERS.limit) params.set("limit", String(filters.limit));
  return params;
}

/** Params object for the API client (arrays become repeated query keys). */
export function filtersToApiParams(filters: ItemFilters): Record<string, unknown> {
  return {
    status: filters.status,
    priority: filters.priority,
    group: filters.group,
    category: filters.category,
    owner_org: filters.owner_org,
    kind: filters.kind,
    assignee_id: filters.assignee_id,
    due_before: filters.due_before,
    due_after: filters.due_after,
    q: filters.q,
    sort: filters.sort,
    direction: filters.direction,
    page: filters.page,
    limit: filters.limit,
  };
}

/** Count of active *content* filters (ignores sort/paging) for the "clear" affordance. */
export function activeFilterCount(filters: ItemFilters): number {
  let n = 0;
  for (const key of ARRAY_KEYS) n += filters[key].length;
  if (filters.kind) n++;
  if (filters.assignee_id != null) n++;
  if (filters.due_before) n++;
  if (filters.due_after) n++;
  if (filters.q) n++;
  return n;
}
```

`frontend/src/features/items/filters.test.ts`:

```ts
import {
  activeFilterCount,
  DEFAULT_FILTERS,
  filtersToSearchParams,
  parseFilters,
} from "./filters";

test("round-trips filters through URL params", () => {
  const filters = {
    ...DEFAULT_FILTERS,
    status: ["open", "blocked"] as const,
    owner_org: ["joint"] as const,
    q: "stability",
    direction: "desc" as const,
    page: 2,
  };
  const params = filtersToSearchParams(filters as never);
  const parsed = parseFilters(params);
  expect(parsed.status).toEqual(["open", "blocked"]);
  expect(parsed.owner_org).toEqual(["joint"]);
  expect(parsed.q).toBe("stability");
  expect(parsed.direction).toBe("desc");
  expect(parsed.page).toBe(2);
});

test("omits defaults from the query string", () => {
  const params = filtersToSearchParams(DEFAULT_FILTERS);
  expect(params.toString()).toBe("");
});

test("counts only content filters", () => {
  expect(activeFilterCount(DEFAULT_FILTERS)).toBe(0);
  expect(activeFilterCount({ ...DEFAULT_FILTERS, status: ["open"], q: "x", page: 3 })).toBe(2);
});
```

Run: `cd frontend && npx vitest run src/features/items/filters.test.ts` → RED then GREEN.

- [ ] **Step 3: Write the data hooks**

`frontend/src/features/items/useItems.ts`:

```ts
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiList } from "@/lib/api/client";
import type { ItemOut, Meta } from "@/lib/api/types";
import { qk } from "@/lib/query";
import { filtersToApiParams, type ItemFilters } from "./filters";

export function useItems(filters: ItemFilters) {
  return useQuery<{ data: ItemOut[]; meta: Meta }>({
    queryKey: qk.items.list(filters),
    queryFn: () => apiList<ItemOut>("/items", { params: filtersToApiParams(filters) as never }),
    placeholderData: keepPreviousData,
  });
}
```

`frontend/src/features/items/useVocab.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { VocabTermOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

/** All vocab terms, split into group/category (active first, by sort_order). */
export function useVocab() {
  const query = useQuery({
    queryKey: qk.vocab.list(),
    queryFn: () => apiFetch<VocabTermOut[]>("/vocab"),
    staleTime: 5 * 60_000,
  });
  const terms = query.data ?? [];
  const pick = (field: "group" | "category") =>
    terms
      .filter((t) => t.field === field)
      .sort((a, b) => a.sort_order - b.sort_order || a.value.localeCompare(b.value));
  return { ...query, groups: pick("group"), categories: pick("category") };
}
```

`frontend/src/features/items/useUsers.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { UserBrief } from "@/lib/api/types";
import { qk } from "@/lib/query";

/** The user directory keyed by id, for resolving and picking assignees. */
export function useUsers() {
  const query = useQuery({
    queryKey: qk.users.list(),
    queryFn: () => apiFetch<UserBrief[]>("/users/directory"),
    staleTime: 5 * 60_000,
  });
  const users = query.data ?? [];
  const byId = new Map(users.map((u) => [u.id, u]));
  return { ...query, users, byId, active: users.filter((u) => u.is_active) };
}
```

- [ ] **Step 4: Run the filter test to verify it passes**

Run: `cd frontend && npx vitest run src/features/items/filters.test.ts`
Expected: PASS (`3 passed`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/types.ts frontend/src/features/items/filters.ts \
  frontend/src/features/items/filters.test.ts frontend/src/features/items/useItems.ts \
  frontend/src/features/items/useVocab.ts frontend/src/features/items/useUsers.ts
git commit -m "feat(frontend): add items data layer with URL-synced filters and resource hooks"
# append your session's Co-Authored-By trailer
```

---

### Task 10: Items table — columns, sorting, pagination, and the items page

**Files:**
- Create: `frontend/src/features/items/columns.tsx`, `ItemsTable.tsx`, `Pagination.tsx`, `ItemsPage.tsx`
- Modify: `frontend/src/app/router.tsx` (route `/items` → `ItemsPage`)
- Test: `frontend/src/features/items/ItemsTable.test.tsx`

Sortable server-side fields (from `backend/app/services/items.py::SORTABLE`): `entry_no, title, group, owner_org, status, priority, raised_on, due_on, updated_at`. Columns without a `sortKey` are display-only.

- [ ] **Step 1: Write the column definitions**

`frontend/src/features/items/columns.tsx`:

```tsx
import type { ReactNode } from "react";
import { DueDate } from "@/components/domain/DueDate";
import { KindBadge } from "@/components/domain/KindBadge";
import { OwnerBadge } from "@/components/domain/OwnerBadge";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { StatusBadge } from "@/components/domain/StatusBadge";
import type { ItemOut, UserBrief } from "@/lib/api/types";

export interface CellContext {
  usersById: Map<number, UserBrief>;
}

export interface ColumnDef {
  id: string;
  header: string;
  sortKey?: string; // backend sort field; omit for display-only columns
  defaultVisible: boolean;
  align?: "right";
  cell: (item: ItemOut, ctx: CellContext) => ReactNode;
}

const dash = <span className="text-fg-subtle">—</span>;

export const COLUMNS: ColumnDef[] = [
  {
    id: "entry_no",
    header: "#",
    sortKey: "entry_no",
    defaultVisible: true,
    align: "right",
    cell: (i) => <span className="tabular-nums text-fg-muted">{i.entry_no}</span>,
  },
  {
    id: "title",
    header: "Title",
    sortKey: "title",
    defaultVisible: true,
    cell: (i) => (
      <span className="flex items-center gap-2">
        <span className="font-medium text-fg">{i.title}</span>
        {i.kind === "note" && <KindBadge kind="note" />}
      </span>
    ),
  },
  { id: "status", header: "Status", sortKey: "status", defaultVisible: true, cell: (i) => <StatusBadge status={i.status} /> },
  { id: "priority", header: "Priority", sortKey: "priority", defaultVisible: true, cell: (i) => <PriorityBadge priority={i.priority} /> },
  { id: "owner_org", header: "Owner", sortKey: "owner_org", defaultVisible: true, cell: (i) => <OwnerBadge owner={i.owner_org} /> },
  { id: "category", header: "Category", defaultVisible: false, cell: (i) => i.category ?? dash },
  { id: "group", header: "Group", sortKey: "group", defaultVisible: false, cell: (i) => <span className="text-fg-muted">{i.group}</span> },
  {
    id: "assignee",
    header: "Assignee",
    defaultVisible: false,
    cell: (i, ctx) =>
      i.assignee_id == null ? dash : (ctx.usersById.get(i.assignee_id)?.name ?? `#${i.assignee_id}`),
  },
  { id: "due_on", header: "Due", sortKey: "due_on", defaultVisible: true, cell: (i) => <DueDate dueOn={i.due_on} /> },
  { id: "updated", header: "Updated", sortKey: "updated_at", defaultVisible: true, cell: (i) => <RelativeTime iso={i.updated_at} /> },
];

export const DEFAULT_VISIBLE: string[] = COLUMNS.filter((c) => c.defaultVisible).map((c) => c.id);
```

- [ ] **Step 2: Write the table and pagination**

`frontend/src/features/items/ItemsTable.tsx`:

```tsx
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import type { ItemOut, UserBrief } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { COLUMNS } from "./columns";

interface Props {
  items: ItemOut[];
  usersById: Map<number, UserBrief>;
  visible: Set<string>;
  sort: string;
  direction: "asc" | "desc";
  onSort: (sortKey: string) => void;
  onOpen: (id: number) => void;
  selectedId: number | null;
}

export function ItemsTable({ items, usersById, visible, sort, direction, onSort, onOpen, selectedId }: Props) {
  const cols = COLUMNS.filter((c) => visible.has(c.id));
  return (
    <div className="overflow-x-auto rounded-lg border border-border bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border">
            {cols.map((col) => (
              <th
                key={col.id}
                scope="col"
                className={cn("px-4 py-2.5 text-left font-medium text-fg-muted", col.align === "right" && "text-right")}
              >
                {col.sortKey ? (
                  <button
                    type="button"
                    onClick={() => onSort(col.sortKey!)}
                    className="inline-flex items-center gap-1 hover:text-fg"
                  >
                    {col.header}
                    <SortIcon active={sort === col.sortKey} direction={direction} />
                  </button>
                ) : (
                  col.header
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              onClick={() => onOpen(item.id)}
              tabIndex={0}
              onKeyDown={(e) => e.key === "Enter" && onOpen(item.id)}
              aria-selected={selectedId === item.id}
              className={cn(
                "cursor-pointer border-b border-border/60 transition-colors last:border-0 hover:bg-surface-2 focus:bg-surface-2 focus:outline-none",
                selectedId === item.id && "bg-accent-weak/40",
              )}
            >
              {cols.map((col) => (
                <td key={col.id} className={cn("px-4 py-3 align-middle", col.align === "right" && "text-right")}>
                  {col.cell(item, { usersById })}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) return <ChevronsUpDown className="size-3.5 opacity-40" aria-hidden />;
  return direction === "asc" ? (
    <ArrowUp className="size-3.5" aria-hidden />
  ) : (
    <ArrowDown className="size-3.5" aria-hidden />
  );
}
```

`frontend/src/features/items/Pagination.tsx`:

```tsx
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Pagination({
  page,
  limit,
  total,
  onPage,
}: {
  page: number;
  limit: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / limit));
  const start = total === 0 ? 0 : (page - 1) * limit + 1;
  const end = Math.min(page * limit, total);
  return (
    <div className="flex items-center justify-between text-sm text-fg-muted">
      <span>
        {start}–{end} of {total}
      </span>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
          <ChevronLeft className="size-4" /> Prev
        </Button>
        <span>
          Page {page} of {pages}
        </span>
        <Button variant="outline" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
          Next <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write the items page**

`frontend/src/features/items/ItemsPage.tsx` (extended in Tasks 11–13):

```tsx
import { useMemo } from "react";
import { ListChecks } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { DEFAULT_VISIBLE } from "./columns";
import { filtersToSearchParams, parseFilters, type ItemFilters } from "./filters";
import { ItemsTable } from "./ItemsTable";
import { Pagination } from "./Pagination";
import { useItems } from "./useItems";
import { useUsers } from "./useUsers";

export function ItemsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = useMemo(() => parseFilters(searchParams), [searchParams]);
  const items = useItems(filters);
  const { byId } = useUsers();
  const visible = new Set(DEFAULT_VISIBLE);

  function apply(next: Partial<ItemFilters>) {
    const merged = { ...filters, ...next };
    if (!("page" in next)) merged.page = 1; // any content/sort change returns to page 1
    const params = filtersToSearchParams(merged);
    const selected = searchParams.get("selected");
    if (selected) params.set("selected", selected);
    setSearchParams(params);
  }

  function onSort(sortKey: string) {
    const direction = filters.sort === sortKey && filters.direction === "asc" ? "desc" : "asc";
    apply({ sort: sortKey, direction });
  }

  function onOpen(id: number) {
    const params = new URLSearchParams(searchParams);
    params.set("selected", String(id));
    setSearchParams(params);
  }

  const selectedId = searchParams.get("selected") ? Number(searchParams.get("selected")) : null;
  const total = items.data?.meta.total ?? 0;
  const rows = items.data?.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Action items</h1>
          <p className="text-sm text-fg-muted">
            {total} item{total === 1 ? "" : "s"}
          </p>
        </div>
      </div>

      {items.isLoading ? (
        <div className="flex flex-col gap-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-12 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState icon={ListChecks} title="No items match" description="Adjust the filters to see more." />
      ) : (
        <>
          <ItemsTable
            items={rows}
            usersById={byId}
            visible={visible}
            sort={filters.sort}
            direction={filters.direction}
            onSort={onSort}
            onOpen={onOpen}
            selectedId={selectedId}
          />
          <Pagination page={filters.page} limit={filters.limit} total={total} onPage={(page) => apply({ page })} />
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Route `/items` to the real page**

In `frontend/src/app/router.tsx`: remove the `ItemsPlaceholder` function, import the page (`import { ItemsPage } from "@/features/items/ItemsPage";`), and change the route to `<Route path="/items" element={<ItemsPage />} />`.

- [ ] **Step 5: Write the failing table test**

`frontend/src/features/items/ItemsTable.test.tsx`:

```tsx
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
      items={[makeItem({ id: 1 }), makeItem({ id: 2, entry_no: 2, kind: "note", status: null, title: "A decision" })]}
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
  expect(screen.getByText("Note")).toBeInTheDocument();
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
```

- [ ] **Step 6: Run the tests and build**

Run: `cd frontend && npx vitest run src/features/items/ItemsTable.test.tsx`
Expected: PASS (`2 passed`).

Run: `cd frontend && npm run build`
Expected: clean build (router now references `ItemsPage`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/items/columns.tsx frontend/src/features/items/ItemsTable.tsx \
  frontend/src/features/items/Pagination.tsx frontend/src/features/items/ItemsPage.tsx \
  frontend/src/features/items/ItemsTable.test.tsx frontend/src/app/router.tsx
git commit -m "feat(frontend): add items table with server-side sort and pagination"
# append your session's Co-Authored-By trailer
```

---

### Task 11: Filter bar, search, and column visibility

**Files:**
- Create: `frontend/src/components/ui/multi-select.tsx`
- Create: `frontend/src/features/items/FilterBar.tsx`, `ColumnChooser.tsx`, `useColumnVisibility.ts`
- Modify: `frontend/src/features/items/ItemsPage.tsx` (render the filter bar + column chooser; use persisted visibility)
- Test: `frontend/src/features/items/FilterBar.test.tsx`

- [ ] **Step 1: Write the generic multi-select**

`frontend/src/components/ui/multi-select.tsx`:

```tsx
import { Check, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/cn";

export interface Option {
  value: string;
  label: string;
}

export function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
}) {
  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          {label}
          {selected.length > 0 && (
            <span className="rounded bg-accent-weak px-1.5 text-xs font-semibold text-accent">
              {selected.length}
            </span>
          )}
          <ChevronDown className="size-3.5 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56 p-1">
        <ul className="max-h-64 overflow-y-auto">
          {options.length === 0 && <li className="px-2 py-1.5 text-sm text-fg-subtle">No options</li>}
          {options.map((opt) => {
            const active = selected.includes(opt.value);
            return (
              <li key={opt.value}>
                <button
                  type="button"
                  onClick={() => toggle(opt.value)}
                  className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-surface-2"
                >
                  <span
                    className={cn(
                      "flex size-4 items-center justify-center rounded border",
                      active ? "border-accent bg-accent text-accent-fg" : "border-border-strong",
                    )}
                  >
                    {active && <Check className="size-3" />}
                  </span>
                  {opt.label}
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
```

- [ ] **Step 2: Write the column-visibility hook and chooser**

`frontend/src/features/items/useColumnVisibility.ts`:

```tsx
import { useCallback, useState } from "react";
import { COLUMNS, DEFAULT_VISIBLE } from "./columns";

const KEY = "cmc-item-columns";

export function useColumnVisibility() {
  const [visible, setVisible] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) return new Set(JSON.parse(raw) as string[]);
    } catch {
      /* storage may be unavailable */
    }
    return new Set(DEFAULT_VISIBLE);
  });

  const toggle = useCallback((id: string) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        localStorage.setItem(KEY, JSON.stringify([...next]));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Title anchors the row and cannot be hidden.
  const columns = COLUMNS.map((c) => ({ id: c.id, header: c.header, locked: c.id === "title" }));
  return { visible, toggle, columns };
}
```

`frontend/src/features/items/ColumnChooser.tsx`:

```tsx
import { Columns3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function ColumnChooser({
  columns,
  visible,
  onToggle,
}: {
  columns: { id: string; header: string; locked: boolean }[];
  visible: Set<string>;
  onToggle: (id: string) => void;
}) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Columns3 className="size-4" /> Columns
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Visible columns</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {columns.map((col) => (
          <DropdownMenuCheckboxItem
            key={col.id}
            checked={visible.has(col.id)}
            disabled={col.locked}
            onCheckedChange={() => onToggle(col.id)}
            onSelect={(e) => e.preventDefault()}
          >
            {col.header}
          </DropdownMenuCheckboxItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 3: Write the filter bar**

`frontend/src/features/items/FilterBar.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { MultiSelect, type Option } from "@/components/ui/multi-select";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { KINDS, OWNER_ORGS, PRIORITIES, STATUSES } from "@/lib/constants";
import { KIND_LABELS, OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "@/lib/labels";
import { activeFilterCount, type ItemFilters } from "./filters";
import { useUsers } from "./useUsers";
import { useVocab } from "./useVocab";

const STATUS_OPTIONS: Option[] = STATUSES.map((v) => ({ value: v, label: STATUS_LABELS[v] }));
const PRIORITY_OPTIONS: Option[] = PRIORITIES.map((v) => ({ value: v, label: PRIORITY_LABELS[v] }));
const OWNER_OPTIONS: Option[] = OWNER_ORGS.map((v) => ({ value: v, label: OWNER_LABELS[v] }));

export function FilterBar({
  filters,
  onChange,
  children,
}: {
  filters: ItemFilters;
  onChange: (next: Partial<ItemFilters>) => void;
  children?: React.ReactNode; // slot for column chooser + new-item button
}) {
  const { groups, categories } = useVocab();
  const { active: users } = useUsers();
  const [q, setQ] = useState(filters.q ?? "");

  useEffect(() => setQ(filters.q ?? ""), [filters.q]);
  useEffect(() => {
    const handle = setTimeout(() => {
      const next = q.trim() || null;
      if (next !== (filters.q ?? null)) onChange({ q: next });
    }, 300);
    return () => clearTimeout(handle);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const count = activeFilterCount(filters);

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-subtle" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search title & details…"
          className="w-64 pl-8"
          aria-label="Search items"
        />
      </div>

      <MultiSelect label="Status" options={STATUS_OPTIONS} selected={filters.status} onChange={(v) => onChange({ status: v as ItemFilters["status"] })} />
      <MultiSelect label="Priority" options={PRIORITY_OPTIONS} selected={filters.priority} onChange={(v) => onChange({ priority: v as ItemFilters["priority"] })} />
      <MultiSelect label="Owner" options={OWNER_OPTIONS} selected={filters.owner_org} onChange={(v) => onChange({ owner_org: v as ItemFilters["owner_org"] })} />
      <MultiSelect label="Group" options={groups.map((g) => ({ value: g.value, label: g.value }))} selected={filters.group} onChange={(v) => onChange({ group: v })} />
      <MultiSelect label="Category" options={categories.map((c) => ({ value: c.value, label: c.value }))} selected={filters.category} onChange={(v) => onChange({ category: v })} />

      <Select
        value={filters.kind ?? "all"}
        onValueChange={(v) => onChange({ kind: v === "all" ? null : (v as ItemFilters["kind"]) })}
      >
        <SelectTrigger className="h-8 w-28">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All kinds</SelectItem>
          {KINDS.map((k) => (
            <SelectItem key={k} value={k}>
              {KIND_LABELS[k]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={filters.assignee_id != null ? String(filters.assignee_id) : "all"}
        onValueChange={(v) => onChange({ assignee_id: v === "all" ? null : Number(v) })}
      >
        <SelectTrigger className="h-8 w-40">
          <SelectValue placeholder="Assignee" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">Any assignee</SelectItem>
          {users.map((u) => (
            <SelectItem key={u.id} value={String(u.id)}>
              {u.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <div className="flex items-center gap-1 text-sm text-fg-muted">
        <span>Due</span>
        <Input
          type="date"
          value={filters.due_after ?? ""}
          onChange={(e) => onChange({ due_after: e.target.value || null })}
          className="h-8 w-36"
          aria-label="Due after"
        />
        <span>–</span>
        <Input
          type="date"
          value={filters.due_before ?? ""}
          onChange={(e) => onChange({ due_before: e.target.value || null })}
          className="h-8 w-36"
          aria-label="Due before"
        />
      </div>

      {count > 0 && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() =>
            onChange({
              status: [],
              priority: [],
              group: [],
              category: [],
              owner_org: [],
              kind: null,
              assignee_id: null,
              due_before: null,
              due_after: null,
              q: null,
            })
          }
        >
          <X className="size-4" /> Clear ({count})
        </Button>
      )}

      <div className="ml-auto flex items-center gap-2">{children}</div>
    </div>
  );
}
```

- [ ] **Step 4: Wire the filter bar and persisted visibility into the items page**

In `frontend/src/features/items/ItemsPage.tsx`:

1. Add imports at the top:

```tsx
import { ColumnChooser } from "./ColumnChooser";
import { FilterBar } from "./FilterBar";
import { useColumnVisibility } from "./useColumnVisibility";
```

2. Remove the `DEFAULT_VISIBLE` import and the line `const visible = new Set(DEFAULT_VISIBLE);`. Replace with:

```tsx
const { visible, toggle, columns } = useColumnVisibility();
```

3. Replace the header `<div className="flex items-center justify-between">…</div>` block with a heading row plus the filter bar (the `New item` button is added in Task 12 via the `children` slot):

```tsx
<div className="flex flex-col gap-4">
  <div>
    <h1 className="text-xl font-semibold">Action items</h1>
    <p className="text-sm text-fg-muted">
      {total} item{total === 1 ? "" : "s"}
    </p>
  </div>
  <FilterBar filters={filters} onChange={apply}>
    <ColumnChooser columns={columns} visible={visible} onToggle={toggle} />
  </FilterBar>
</div>
```

(Keep the rest of the page — loading skeleton, empty state, table, pagination — unchanged. `total` is already computed above; if the header now precedes that line, move the `const total`/`const rows` computations above the returned JSX.)

- [ ] **Step 5: Write the failing filter-bar test**

`frontend/src/features/items/FilterBar.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DEFAULT_FILTERS } from "./filters";
import { FilterBar } from "./FilterBar";

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/vocab")
      ? { success: true, data: [{ id: 1, program_id: 1, field: "group", value: "General Issues", sort_order: 0, is_active: true }], error: null, meta: null }
      : url.includes("/users/directory")
        ? { success: true, data: [{ id: 5, name: "Mo Member", org: "yarrow", is_active: true }], error: null, meta: null }
        : { success: true, data: [], error: null, meta: null };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

function renderBar() {
  mockFetch();
  const onChange = vi.fn();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <FilterBar filters={DEFAULT_FILTERS} onChange={onChange} />
    </QueryClientProvider>,
  );
  return onChange;
}

afterEach(() => vi.restoreAllMocks());

test("selecting a status calls onChange with that value", async () => {
  const onChange = renderBar();
  await userEvent.click(screen.getByRole("button", { name: /^status/i }));
  await userEvent.click(await screen.findByText("Open"));
  expect(onChange).toHaveBeenCalledWith({ status: ["open"] });
});

test("typing in search debounces into onChange", async () => {
  const onChange = renderBar();
  await userEvent.type(screen.getByLabelText(/search items/i), "stability");
  await waitFor(() => expect(onChange).toHaveBeenCalledWith({ q: "stability" }));
});
```

- [ ] **Step 6: Run the tests and build**

Run: `cd frontend && npx vitest run src/features/items/FilterBar.test.tsx`
Expected: PASS (`2 passed`).

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/multi-select.tsx frontend/src/features/items/FilterBar.tsx \
  frontend/src/features/items/ColumnChooser.tsx frontend/src/features/items/useColumnVisibility.ts \
  frontend/src/features/items/ItemsPage.tsx frontend/src/features/items/FilterBar.test.tsx
git commit -m "feat(frontend): add filter bar, search, and persisted column visibility"
# append your session's Co-Authored-By trailer
```

---

### Task 12: Item create — shared form, mutations, and the New-item dialog

**Files:**
- Create: `frontend/src/features/items/item-schema.ts`, `useItem.ts`, `useItemMutations.ts`, `ItemForm.tsx`, `NewItemButton.tsx`
- Modify: `frontend/src/features/items/ItemsPage.tsx` (add the New-item button to the filter bar slot)
- Test: `frontend/src/features/items/item-schema.test.ts`

- [ ] **Step 1: Write the form schema with a failing test**

`frontend/src/features/items/item-schema.ts`:

```ts
import { z } from "zod";
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
```

`frontend/src/features/items/item-schema.test.ts`:

```ts
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
```

Run: `cd frontend && npx vitest run src/features/items/item-schema.test.ts` → RED then GREEN.

- [ ] **Step 2: Write the item query and mutation hooks**

`frontend/src/features/items/useItem.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ItemOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useItem(id: number | null) {
  return useQuery({
    queryKey: id != null ? qk.items.detail(id) : ["items", "detail", "none"],
    queryFn: () => apiFetch<ItemOut>(`/items/${id}`),
    enabled: id != null,
  });
}
```

`frontend/src/features/items/useItemMutations.ts`:

```ts
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { ItemCreate, ItemOut, ItemPatch } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useCreateItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ItemCreate) => apiFetch<ItemOut>("/items", { method: "POST", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.items.all() }),
  });
}

export function usePatchItem(id: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ItemPatch) => apiFetch<ItemOut>(`/items/${id}`, { method: "PATCH", body }),
    onSuccess: (item) => {
      qc.setQueryData(qk.items.detail(id), item);
      qc.invalidateQueries({ queryKey: qk.items.all() });
      qc.invalidateQueries({ queryKey: qk.items.history(id) });
    },
  });
}

export function useDeleteItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<ItemOut>(`/items/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.items.all() }),
  });
}

export function useRestoreItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => apiFetch<ItemOut>(`/items/${id}/restore`, { method: "POST" }),
    onSuccess: (item) => {
      qc.setQueryData(qk.items.detail(item.id), item);
      qc.invalidateQueries({ queryKey: qk.items.all() });
    },
  });
}
```

- [ ] **Step 3: Write the shared item form**

`frontend/src/features/items/ItemForm.tsx` (reused by the create dialog now and the detail editor in Task 13):

```tsx
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

function Field({ label, error, children }: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
      {error && <p className="text-sm text-danger">{error}</p>}
    </div>
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
              <Input value={field.value ?? ""} onChange={(e) => field.onChange(e.target.value || null)} />
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
```

- [ ] **Step 4: Write the New-item dialog**

`frontend/src/features/items/NewItemButton.tsx`:

```tsx
import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useToast } from "@/lib/toast";
import { ItemForm } from "./ItemForm";
import { NEW_ITEM_DEFAULTS } from "./item-schema";
import { useCreateItem } from "./useItemMutations";
import { useVocab } from "./useVocab";

export function NewItemButton() {
  const [open, setOpen] = useState(false);
  const create = useCreateItem();
  const { toast } = useToast();
  const { groups } = useVocab();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">
          <Plus className="size-4" /> New item
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>New item</DialogTitle>
        </DialogHeader>
        <div className="overflow-y-auto px-6 py-4">
          <ItemForm
            defaultValues={{ ...NEW_ITEM_DEFAULTS, group: groups[0]?.value ?? "" }}
            submitLabel="Create item"
            onCancel={() => setOpen(false)}
            onSubmit={async (payload) => {
              const item = await create.mutateAsync(payload);
              toast({ title: `Created #${item.entry_no}`, variant: "success" });
              setOpen(false);
            }}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 5: Add the button to the items page filter bar**

In `frontend/src/features/items/ItemsPage.tsx`, import `NewItemButton` and add it inside the `<FilterBar>` slot after `<ColumnChooser…/>`:

```tsx
import { NewItemButton } from "./NewItemButton";
// …
<FilterBar filters={filters} onChange={apply}>
  <ColumnChooser columns={columns} visible={visible} onToggle={toggle} />
  <NewItemButton />
</FilterBar>
```

- [ ] **Step 6: Run the schema test and build**

Run: `cd frontend && npx vitest run src/features/items/item-schema.test.ts`
Expected: PASS (`2 passed`).

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/items/item-schema.ts frontend/src/features/items/item-schema.test.ts \
  frontend/src/features/items/useItem.ts frontend/src/features/items/useItemMutations.ts \
  frontend/src/features/items/ItemForm.tsx frontend/src/features/items/NewItemButton.tsx \
  frontend/src/features/items/ItemsPage.tsx
git commit -m "feat(frontend): add item create form, mutations, and New-item dialog"
# append your session's Co-Authored-By trailer
```

---

### Task 13: Item detail — side sheet, deep-link route, and editable Details tab

**Files:**
- Modify: `frontend/src/features/items/item-schema.ts` (add `itemToFormValues`)
- Create: `frontend/src/features/item-detail/ItemDetail.tsx`, `DetailsTab.tsx`, `ItemDetailSheet.tsx`, `ItemDetailPage.tsx`
- Create placeholders (filled in Tasks 14–15): `frontend/src/features/item-detail/UpdatesTab.tsx`, `HistoryTab.tsx`
- Modify: `frontend/src/features/items/ItemsPage.tsx` (render `<ItemDetailSheet/>`)
- Modify: `frontend/src/app/router.tsx` (add `/items/:id`)
- Test: `frontend/src/features/item-detail/ItemDetail.test.tsx`

- [ ] **Step 1: Add the ItemOut → form-values mapper**

Append to `frontend/src/features/items/item-schema.ts`:

```ts
import type { ItemOut } from "@/lib/api/types";

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
```

- [ ] **Step 2: Write the placeholder tabs (replaced in Tasks 14–15)**

`frontend/src/features/item-detail/UpdatesTab.tsx`:

```tsx
export function UpdatesTab({ itemId }: { itemId: number }) {
  return <p className="text-sm text-fg-muted">Update timeline for #{itemId} arrives in Task 14.</p>;
}
```

`frontend/src/features/item-detail/HistoryTab.tsx`:

```tsx
export function HistoryTab({ itemId }: { itemId: number }) {
  return <p className="text-sm text-fg-muted">History for #{itemId} arrives in Task 15.</p>;
}
```

- [ ] **Step 3: Write the Details tab and the ItemDetail body**

`frontend/src/features/item-detail/DetailsTab.tsx`:

```tsx
import type { ItemOut } from "@/lib/api/types";
import { useToast } from "@/lib/toast";
import { ItemForm } from "@/features/items/ItemForm";
import { itemToFormValues } from "@/features/items/item-schema";
import { usePatchItem } from "@/features/items/useItemMutations";

export function DetailsTab({ item }: { item: ItemOut }) {
  const patch = usePatchItem(item.id);
  const { toast } = useToast();
  return (
    <ItemForm
      // `kind` is included in the payload but ignored by the PATCH endpoint (kind is immutable).
      defaultValues={itemToFormValues(item)}
      submitLabel="Save changes"
      onSubmit={async (payload) => {
        await patch.mutateAsync(payload);
        toast({ title: "Changes saved", variant: "success" });
      }}
    />
  );
}
```

`frontend/src/features/item-detail/ItemDetail.tsx`:

```tsx
import { RotateCcw, Trash2 } from "lucide-react";
import { OwnerBadge } from "@/components/domain/OwnerBadge";
import { PriorityBadge } from "@/components/domain/PriorityBadge";
import { StatusBadge } from "@/components/domain/StatusBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ApiError } from "@/lib/api/client";
import { useToast } from "@/lib/toast";
import { useAuth } from "@/features/auth/useAuth";
import { useItem } from "@/features/items/useItem";
import { useDeleteItem, useRestoreItem } from "@/features/items/useItemMutations";
import { DetailsTab } from "./DetailsTab";
import { HistoryTab } from "./HistoryTab";
import { UpdatesTab } from "./UpdatesTab";

export function ItemDetail({ itemId, onClose }: { itemId: number; onClose?: () => void }) {
  const { data: item, isLoading, isError, error } = useItem(itemId);
  const { user } = useAuth();
  const del = useDeleteItem();
  const restore = useRestoreItem();
  const { toast } = useToast();

  if (isLoading) {
    return (
      <div className="space-y-3 p-6">
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }
  if (isError || !item) {
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <div className="p-6 text-sm text-danger">
        {gone ? "This item no longer exists." : "Could not load this item."}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-6 py-4 pr-10">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs text-fg-muted">#{item.entry_no}</p>
            <h2 className="text-lg font-semibold">{item.title}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={item.status} />
              <PriorityBadge priority={item.priority} />
              <OwnerBadge owner={item.owner_org} />
              {item.deleted_at && <Badge variant="outline">Deleted</Badge>}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {item.deleted_at
              ? user?.role === "admin" && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={async () => {
                      await restore.mutateAsync(item.id);
                      toast({ title: "Item restored", variant: "success" });
                    }}
                  >
                    <RotateCcw className="size-4" /> Restore
                  </Button>
                )
              : !item.deleted_at && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={async () => {
                      await del.mutateAsync(item.id);
                      toast({ title: "Item deleted", variant: "success" });
                      onClose?.();
                    }}
                  >
                    <Trash2 className="size-4" /> Delete
                  </Button>
                )}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        <Tabs defaultValue="details">
          <TabsList className="mb-4">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="updates">Updates</TabsTrigger>
            <TabsTrigger value="history">History</TabsTrigger>
          </TabsList>
          <TabsContent value="details">
            <DetailsTab item={item} />
          </TabsContent>
          <TabsContent value="updates">
            <UpdatesTab itemId={item.id} />
          </TabsContent>
          <TabsContent value="history">
            <HistoryTab itemId={item.id} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write the sheet wrapper and the full-page route**

`frontend/src/features/item-detail/ItemDetailSheet.tsx`:

```tsx
import { useSearchParams } from "react-router-dom";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { ItemDetail } from "./ItemDetail";

/** Reads `?selected=<id>` and shows the item in a right-side sheet over the list. */
export function ItemDetailSheet() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selected = searchParams.get("selected");
  const id = selected ? Number(selected) : null;

  function close() {
    const params = new URLSearchParams(searchParams);
    params.delete("selected");
    setSearchParams(params);
  }

  return (
    <Sheet open={id != null} onOpenChange={(open) => !open && close()}>
      <SheetContent className="p-0" aria-describedby={undefined}>
        {id != null && <ItemDetail itemId={id} onClose={close} />}
      </SheetContent>
    </Sheet>
  );
}
```

`frontend/src/features/item-detail/ItemDetailPage.tsx`:

```tsx
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { NotFound } from "@/app/NotFound";
import { ItemDetail } from "./ItemDetail";

/** Full-page detail for deep links (e.g. shared URLs, refresh on /items/42). */
export function ItemDetailPage() {
  const { id } = useParams();
  const itemId = id ? Number(id) : NaN;
  if (Number.isNaN(itemId)) return <NotFound />;
  return (
    <div className="mx-auto max-w-3xl">
      <Button asChild={false} variant="ghost" size="sm" className="mb-3">
        <Link to="/items">
          <ArrowLeft className="size-4" /> Back to items
        </Link>
      </Button>
      <div className="rounded-lg border border-border bg-surface">
        <ItemDetail itemId={itemId} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Render the sheet on the items page and add the route**

In `frontend/src/features/items/ItemsPage.tsx`: import `ItemDetailSheet` and render it once at the end of the page's root `<div className="flex flex-col gap-4">` (after the pagination block):

```tsx
import { ItemDetailSheet } from "@/features/item-detail/ItemDetailSheet";
// … at the end of the returned tree, as the last child:
<ItemDetailSheet />
```

In `frontend/src/app/router.tsx`: import the page and add the route inside the `AppLayout` block, next to `/items`:

```tsx
import { ItemDetailPage } from "@/features/item-detail/ItemDetailPage";
// …
<Route path="/items/:id" element={<ItemDetailPage />} />
```

- [ ] **Step 6: Write the failing detail test**

`frontend/src/features/item-detail/ItemDetail.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/lib/toast";
import { ItemDetail } from "./ItemDetail";

function itemJson() {
  return {
    id: 7, program_id: 1, entry_no: 7, kind: "action", title: "Confirm EP compliance",
    details: "line two", group: "General Issues", category: "QA", owner_org: "gensci",
    assignee_id: null, status: "open", priority: "p1", raised_on: "2026-02-05", source: null,
    due_on: "2026-03-01", completed_on: null, notes_risks: "", file_path: "", created_by: 1,
    created_at: "2026-02-05T00:00:00", updated_by: 1, updated_at: "2026-02-06T00:00:00",
    deleted_at: null, last_update_on: null,
  };
}

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    let body: unknown = { success: true, data: [], error: null, meta: null };
    if (url.includes("/items/7")) body = { success: true, data: itemJson(), error: null, meta: null };
    else if (url.includes("/auth/me"))
      body = { success: true, data: { id: 1, name: "A", email: "a@b.co", org: "gensci", role: "member", is_active: true, last_login_at: null, created_at: "2026-01-01T00:00:00" }, error: null, meta: null };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

afterEach(() => vi.restoreAllMocks());

test("loads and renders an item with the editable Details tab", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <TooltipProvider>
          <ItemDetail itemId={7} />
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByRole("heading", { name: /confirm ep compliance/i })).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: /save changes/i })).toBeInTheDocument();
});
```

- [ ] **Step 7: Run the test and build**

Run: `cd frontend && npx vitest run src/features/item-detail/ItemDetail.test.tsx`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/items/item-schema.ts frontend/src/features/item-detail \
  frontend/src/features/items/ItemsPage.tsx frontend/src/app/router.tsx
git commit -m "feat(frontend): add item detail sheet, deep-link route, and editable Details tab"
# append your session's Co-Authored-By trailer
```

---

### Task 14: Update timeline — compose, list, edit, delete

**Files:**
- Create: `frontend/src/features/item-detail/useUpdates.ts`
- Replace: `frontend/src/features/item-detail/UpdatesTab.tsx` (real implementation)
- Test: `frontend/src/features/item-detail/UpdatesTab.test.tsx`

Permissions (spec §6): any user posts updates and edits/deletes their **own**; admins edit/delete **any**. The backend enforces this; the UI hides controls the user cannot use.

- [ ] **Step 1: Write the update hooks**

`frontend/src/features/item-detail/useUpdates.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { UpdateOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useItemUpdates(itemId: number) {
  return useQuery({
    queryKey: qk.items.updates(itemId),
    queryFn: () => apiFetch<UpdateOut[]>(`/items/${itemId}/updates`),
  });
}

/** Invalidate the timeline, the item (updated_at/last_update_on change), the list, and history. */
function invalidateAround(qc: ReturnType<typeof useQueryClient>, itemId: number) {
  qc.invalidateQueries({ queryKey: qk.items.updates(itemId) });
  qc.invalidateQueries({ queryKey: qk.items.detail(itemId) });
  qc.invalidateQueries({ queryKey: qk.items.all() });
  qc.invalidateQueries({ queryKey: qk.items.history(itemId) });
}

export function useCreateUpdate(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { body: string; occurred_on: string | null }) =>
      apiFetch<UpdateOut>(`/items/${itemId}/updates`, { method: "POST", body }),
    onSuccess: () => invalidateAround(qc, itemId),
  });
}

export function usePatchUpdate(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...patch }: { id: number; body?: string; occurred_on?: string | null }) =>
      apiFetch<UpdateOut>(`/items/${itemId}/updates/${id}`, { method: "PATCH", body: patch }),
    onSuccess: () => invalidateAround(qc, itemId),
  });
}

export function useDeleteUpdate(itemId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<null>(`/items/${itemId}/updates/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateAround(qc, itemId),
  });
}
```

- [ ] **Step 2: Write the timeline tab**

Replace `frontend/src/features/item-detail/UpdatesTab.tsx` with:

```tsx
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
import {
  useCreateUpdate,
  useDeleteUpdate,
  useItemUpdates,
  usePatchUpdate,
} from "./useUpdates";

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
        <EmptyState icon={MessageSquare} title="No updates yet" description="Post the first update above." />
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
          <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={3} aria-label="Edit update body" />
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
```

- [ ] **Step 3: Write the failing timeline test**

`frontend/src/features/item-detail/UpdatesTab.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/lib/toast";
import { UpdatesTab } from "./UpdatesTab";

function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (url.includes("/auth/me")) {
      return json({ success: true, data: { id: 5, name: "Mo Member", email: "m@y.co", org: "yarrow", role: "member", is_active: true, last_login_at: null, created_at: "2026-01-01T00:00:00" }, error: null, meta: null });
    }
    if (url.includes("/updates") && method === "POST") {
      return json({ success: true, data: newUpdate(), error: null, meta: null });
    }
    if (url.includes("/updates")) {
      return json({ success: true, data: [existingUpdate()], error: null, meta: null });
    }
    return json({ success: true, data: [], error: null, meta: null });
  });
}

const json = (body: unknown) =>
  new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
const existingUpdate = () => ({ id: 1, item_id: 9, author_id: 5, author_name: "Mo Member", author_org: "yarrow", body: "Stability data received", occurred_on: "2026-02-10", created_at: "2026-02-10T00:00:00", edited_at: null });
const newUpdate = () => ({ ...existingUpdate(), id: 2, body: "Sent to QA" });

function renderTab() {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <UpdatesTab itemId={9} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => vi.restoreAllMocks());

test("lists existing updates and posts a new one", async () => {
  renderTab();
  expect(await screen.findByText("Stability data received")).toBeInTheDocument();

  await userEvent.type(screen.getByLabelText(/new update body/i), "Sent to QA");
  await userEvent.click(screen.getByRole("button", { name: /post update/i }));

  await waitFor(() =>
    expect(
      (globalThis.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls.some(
        ([u, i]) => String(u).includes("/updates") && (i?.method ?? "GET") === "POST",
      ),
    ).toBe(true),
  );
});
```

- [ ] **Step 4: Run the test and build**

Run: `cd frontend && npx vitest run src/features/item-detail/UpdatesTab.test.tsx`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/item-detail/useUpdates.ts \
  frontend/src/features/item-detail/UpdatesTab.tsx \
  frontend/src/features/item-detail/UpdatesTab.test.tsx
git commit -m "feat(frontend): add item update timeline with compose, edit, and delete"
# append your session's Co-Authored-By trailer
```

---

### Task 15: History tab — audit event timeline with field diffs

**Files:**
- Create: `frontend/src/features/item-detail/useHistory.ts`
- Create: `frontend/src/components/domain/DiffTable.tsx`
- Replace: `frontend/src/features/item-detail/HistoryTab.tsx` (real implementation)
- Test: `frontend/src/features/item-detail/HistoryTab.test.tsx`

- [ ] **Step 1: Write the history hook**

`frontend/src/features/item-detail/useHistory.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import type { AuditEventOut } from "@/lib/api/types";
import { qk } from "@/lib/query";

export function useItemHistory(itemId: number) {
  return useQuery({
    queryKey: qk.items.history(itemId),
    queryFn: () => apiFetch<AuditEventOut[]>(`/items/${itemId}/history`),
  });
}
```

- [ ] **Step 2: Write the diff table**

`frontend/src/components/domain/DiffTable.tsx`:

```tsx
import type { Priority, Status } from "@/lib/constants";
import type { OwnerOrg } from "@/lib/constants";
import type { UserBrief } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { OWNER_LABELS, PRIORITY_LABELS, STATUS_LABELS } from "@/lib/labels";

const FIELD_LABELS: Record<string, string> = {
  title: "Title",
  details: "Details",
  group: "Group",
  category: "Category",
  owner_org: "Owner",
  assignee_id: "Assignee",
  status: "Status",
  priority: "Priority",
  raised_on: "Raised on",
  source: "Source",
  due_on: "Due",
  completed_on: "Completed",
  notes_risks: "Notes / risks",
  file_path: "File path",
  kind: "Kind",
};

function fieldLabel(field: string): string {
  return FIELD_LABELS[field] ?? field;
}

function formatValue(field: string, value: unknown, usersById: Map<number, UserBrief>): string {
  if (value === null || value === undefined || value === "") return "—";
  if (field === "status") return STATUS_LABELS[value as Status] ?? String(value);
  if (field === "priority") return PRIORITY_LABELS[value as Priority] ?? String(value);
  if (field === "owner_org") return OWNER_LABELS[value as OwnerOrg] ?? String(value);
  if (field === "assignee_id") return usersById.get(Number(value))?.name ?? `#${value}`;
  if (field === "raised_on" || field === "due_on" || field === "completed_on")
    return formatDate(String(value));
  return String(value);
}

export function DiffTable({
  changes,
  usersById,
}: {
  changes: Record<string, { old?: unknown; new?: unknown }>;
  usersById: Map<number, UserBrief>;
}) {
  return (
    <table className="mt-2 w-full text-sm">
      <tbody>
        {Object.entries(changes).map(([field, diff]) => (
          <tr key={field} className="align-top">
            <td className="w-28 py-1 pr-3 text-fg-muted">{fieldLabel(field)}</td>
            <td className="py-1">
              <span className="text-fg-subtle line-through">
                {formatValue(field, diff.old, usersById)}
              </span>
              <span className="mx-1.5 text-fg-subtle">→</span>
              <span className="text-fg">{formatValue(field, diff.new, usersById)}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 3: Write the history tab**

Replace `frontend/src/features/item-detail/HistoryTab.tsx` with:

```tsx
import { History } from "lucide-react";
import { DiffTable } from "@/components/domain/DiffTable";
import { RelativeTime } from "@/components/domain/RelativeTime";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useUsers } from "@/features/items/useUsers";
import { useItemHistory } from "./useHistory";

export function HistoryTab({ itemId }: { itemId: number }) {
  const history = useItemHistory(itemId);
  const { byId } = useUsers();
  const events = history.data ?? [];

  if (history.isLoading) return <Skeleton className="h-24 w-full" />;
  if (events.length === 0)
    return <EmptyState icon={History} title="No history yet" description="Changes will appear here." />;

  return (
    <ol className="flex flex-col gap-4">
      {events.map((e) => {
        const changes = (e.changes ?? {}) as Record<string, { old?: unknown; new?: unknown }>;
        return (
          <li key={e.id} className="relative border-l border-border pl-4">
            <span className="absolute -left-1 top-1.5 size-2 rounded-full bg-accent" aria-hidden />
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-medium">{e.actor_name}</span>
              <span className="text-fg-muted">{e.summary}</span>
              <span className="text-fg-subtle">·</span>
              <RelativeTime iso={e.occurred_at} />
            </div>
            {Object.keys(changes).length > 0 && <DiffTable changes={changes} usersById={byId} />}
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 4: Write the failing history test**

`frontend/src/features/item-detail/HistoryTab.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HistoryTab } from "./HistoryTab";

function mockFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    const body = url.includes("/history")
      ? {
          success: true,
          data: [
            {
              id: 1, program_id: 1, entity_type: "item", entity_id: 3, action: "status_changed",
              actor_id: 5, actor_name: "Mo Member", actor_org: "yarrow",
              occurred_at: "2026-02-11T00:00:00", summary: "changed status Open → Blocked",
              changes: { status: { old: "open", new: "blocked" } },
            },
          ],
          error: null, meta: null,
        }
      : { success: true, data: [], error: null, meta: null };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
}

afterEach(() => vi.restoreAllMocks());

test("renders an audit event with a field diff using human labels", async () => {
  mockFetch();
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <HistoryTab itemId={3} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/changed status open → blocked/i)).toBeInTheDocument();
  expect(screen.getByText("Open")).toBeInTheDocument(); // old value, humanized
  expect(screen.getByText("Blocked")).toBeInTheDocument(); // new value, humanized
});
```

- [ ] **Step 5: Run the test and build**

Run: `cd frontend && npx vitest run src/features/item-detail/HistoryTab.test.tsx`
Expected: PASS (`1 passed`).

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/item-detail/useHistory.ts frontend/src/components/domain/DiffTable.tsx \
  frontend/src/features/item-detail/HistoryTab.tsx frontend/src/features/item-detail/HistoryTab.test.tsx
git commit -m "feat(frontend): add item history tab with audit field diffs"
# append your session's Co-Authored-By trailer
```

---

### Task 16: Serve the SPA from one container — Docker Node stage + FastAPI SPA fallback

**Files:**
- Modify: `backend/app/main.py` (add `SPAStaticFiles`, use it for the mount)
- Modify: `Dockerfile` (add the `frontend-build` stage; copy `dist` → `/app/static`)
- Modify: `README.md` (note the served UI and the dev proxy)
- Test: `backend/tests/api/test_spa.py`

The API is mounted at `/api` before the static mount, so `/api/*` routes resolve first. The SPA fallback serves `index.html` for unknown non-API paths (so deep links like `/items/42` survive a refresh) while leaving unknown `/api/*` paths to the envelope 404 handler.

- [ ] **Step 1: Write the failing SPA test**

`backend/tests/api/test_spa.py`:

```python
"""The built SPA is served with a client-side-routing fallback that never shadows the API."""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.constants import CSRF_HEADER, CSRF_VALUE
from app.main import create_app


def test_spa_fallback_and_api_404(tmp_path, monkeypatch):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>CMC</title>", encoding="utf-8")
    monkeypatch.setenv("STATIC_DIR", str(static))
    get_settings.cache_clear()
    try:
        client = TestClient(create_app(), headers={CSRF_HEADER: CSRF_VALUE})

        # A deep client-side route returns the SPA shell.
        deep = client.get("/items/42")
        assert deep.status_code == 200
        assert "text/html" in deep.headers["content-type"]
        assert "<title>CMC</title>" in deep.text

        # An unknown API route still returns the JSON envelope 404, not the SPA.
        missing = client.get("/api/does-not-exist")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "http_error"
    finally:
        get_settings.cache_clear()
```

Run: `cd backend && uv run pytest tests/api/test_spa.py -v`
Expected: FAIL — `/items/42` currently 404s (no SPA fallback).

- [ ] **Step 2: Add `SPAStaticFiles` and use it**

In `backend/app/main.py`, add this class at module level (after `_validation_fields`, before `create_app`):

```python
class SPAStaticFiles(StaticFiles):
    """Serve the built SPA, falling back to index.html for client-side routes.

    Unknown ``/api/*`` paths keep the JSON envelope 404 instead of the SPA shell.
    """

    async def get_response(self, path: str, scope):
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404, detail="Not Found")
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise
```

Then change the mount (replace the `app.mount("/", StaticFiles(...))` line):

```python
    static_dir = Path(settings.static_dir)
    if static_dir.is_dir():
        app.mount("/", SPAStaticFiles(directory=str(static_dir), html=True), name="static")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict[str, str]:
            return {"name": app.title, "version": __version__, "docs": "/api/docs"}

    return app
```

- [ ] **Step 3: Run the SPA test and the full backend suite**

Run: `cd backend && uv run pytest tests/api/test_spa.py -v`
Expected: PASS (`1 passed`).

Run: `cd backend && uv run pytest`
Expected: all pass, including the existing `test_errors.py::test_unknown_api_route_uses_envelope` (unchanged behavior for `/api/*`).

- [ ] **Step 4: Add the frontend build stage to the Dockerfile**

Replace `Dockerfile` with:

```dockerfile
# syntax=docker/dockerfile:1.7

# 1) Build the frontend into static assets. openapi.json and src/lib/api/schema.d.ts are
#    committed, so this stage needs no running backend.
FROM node:26-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Install backend dependencies with uv.
FROM python:3.14-slim AS backend-deps
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev
COPY backend/ ./

# 3) Slim runtime serving the API and the built frontend on one port.
FROM python:3.14-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /import \
    && chown app:app /data /import
COPY --from=backend-deps --chown=app:app /app /app
COPY --from=frontend-build --chown=app:app /frontend/dist /app/static
RUN chmod +x /app/entrypoint.sh
USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).status == 200 else 1)"
ENTRYPOINT ["/app/entrypoint.sh"]
```

`.dockerignore` already excludes `**/node_modules` and `frontend/dist` and keeps `frontend/` source in context — no change needed. The runtime serves `/app/static` because `settings.static_dir` defaults to `static` and the working directory is `/app`.

- [ ] **Step 5: Note the UI in the README**

In `README.md`, under "## Run it with Docker (the supported way)", add after the `docker compose up` block:

```markdown
Open http://localhost:8000 for the web UI (the same container serves the API and the
built frontend). The API docs remain at http://localhost:8000/api/docs.
```

And add a short develop-the-frontend note under "## Develop locally":

```markdown
### Frontend

```bash
cd frontend
npm install
npm run dev        # Vite on :5173, proxies /api to the backend on :8000
npm test           # Vitest
npm run build      # type-check + build into frontend/dist (served from /app/static in Docker)
```

Regenerate the API types after any backend DTO change:

```bash
cd backend && uv run python -c "import json; from app.main import create_app; print(json.dumps(create_app().openapi()))" > ../frontend/openapi.json
cd ../frontend && npm run gen:api
```
```

- [ ] **Step 6: Build the image (needs Docker) and smoke-check the UI**

Run (only where Docker is available): `docker compose build`
Expected: the `frontend-build` stage runs `npm ci` + `npm run build`, and the runtime image contains `/app/static/index.html`.

Optional end-to-end: `docker compose up -d` then `curl -sSI http://localhost:8000/` shows `200` with `content-type: text/html`; `curl -sS http://localhost:8000/api/health` returns `"database":"ok"`. Then `docker compose down`.

If Docker is unavailable in this environment, note that in the dev log and rely on the `test_spa.py` unit coverage for the fallback behavior; the image build is verified in Phase 4 CI.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/tests/api/test_spa.py Dockerfile README.md
git commit -m "feat: serve the built SPA from the container with a client-side routing fallback"
# append your session's Co-Authored-By trailer
```

---

### Task 17: Final gates, checklist, and Phase 2 dev log

**Files:**
- Modify: `docs/superpowers/implementation-checklist.md` (tick Phase 2 boxes)
- Create: `docs/superpowers/logs/2026-09-06-phase2-dev-log.md`

Note on test tooling: Phase 2 tests mock the network with direct `vi.spyOn(globalThis, "fetch")`, which keeps them dependency-light. MSW and a shared `renderWithProviders` helper are deferred to Phase 3 when the larger component suite (board, dashboard, admin) lands; drop the `test/msw/*` and `test/utils.tsx` placeholders from the file-structure map if they were stubbed.

- [ ] **Step 1: Run every frontend gate**

Run: `cd frontend && npm run typecheck`
Expected: no type errors.

Run: `cd frontend && npm test`
Expected: all suites pass (theme, format, button, StatusBadge, client, query, auth-schema, LoginPage, ProtectedRoute, filters, ItemsTable, FilterBar, item-schema, ItemDetail, UpdatesTab, HistoryTab).

Run: `cd frontend && npm run lint`
Expected: ESLint and Prettier both clean. Fix findings with `npm run format` and targeted edits; re-run until clean.

Run: `cd frontend && npm run build`
Expected: production build succeeds and writes `frontend/dist/`.

- [ ] **Step 2: Run every backend gate (guard against regressions from Tasks 8 & 16)**

Run: `cd backend && uv run pytest`
Expected: all pass (Phase 1 count + the directory tests + the SPA test).

Run: `cd backend && uv run ruff check app tests`
Expected: all checks pass.

- [ ] **Step 3: Update the implementation checklist**

In `docs/superpowers/implementation-checklist.md`, under "## Phase 2 — Frontend core", tick the delivered items and add the plan link at the top of that section:

```markdown
## Phase 2 — Frontend core (own plan required)

Deliverable: both teams use it from one container. Add a Node build stage to the Dockerfile and serve `static/`.

**Plan:** `docs/superpowers/plans/2026-09-06-phase2-frontend-core.md`.

- [x] Write the Phase 2 implementation plan (writing-plans skill).
- [x] Vite + React + TS + Tailwind scaffold; app shell (router, providers, layout).
- [x] Generated TypeScript client from the FastAPI OpenAPI schema.
- [x] Auth: login page, accept-invite/reset page, session-expiry redirect, global error boundary.
- [x] Items table: sortable columns, filter bar, search, column visibility, URL-synced filters.
- [x] Item detail (side sheet + deep-link route): editable fields, update timeline compose box, History tab with audit diffs.
- [x] Envelope-aware API layer (TanStack Query, react-hook-form + zod), inline field errors + toasts.
- [x] Dockerfile Node stage builds frontend into `static/`; single container serves API + UI.
```

(Leave every item beyond `[x]` as-is if a step was genuinely skipped — do not tick what you did not build. The list above reflects the full Phase 2 scope this plan delivers, plus the backend user-directory enabler recorded in the dev log.)

- [ ] **Step 4: Write the Phase 2 dev log**

`docs/superpowers/logs/2026-09-06-phase2-dev-log.md`:

```markdown
# Phase 2 Development Log

Branch: `claude/phase-2-frontend-plan-p8h3e5`. Started 2026-09-06.
Records notable decisions, deviations, and fixes during Phase 2 (frontend core).
Routine "wrote file → tests passed → committed" steps are not logged.

## Environment
- node (≥ 26), npm, backend from Phase 1 (uv, python 3.14).

## Decisions & deviations
- **Design skill unavailable.** The spec's `frontend-design` skill is not present in this
  environment; the org `design` plugin is workflow tooling (Figma/critique), not a code
  generator. The §10 visual direction was encoded directly as a Tailwind v4 CSS-variable
  token system (Task 2) and applied through the primitives (Task 3).
- **Backend enabler (Task 8).** Added `GET /users/directory` (id, name, org, is_active) readable
  by any authenticated user, because the admin-only `GET /users` could not resolve assignee
  names for members. Read-only, no audit, no new permission — consistent with spec §6.
- **Generated types, hand-written envelope.** DTOs come from `openapi-typescript`
  (`openapi.json` committed for offline builds); the `{success,data,error,meta}` envelope and the
  filter/query shapes are hand-written in `src/lib/api`.
- **SPA fallback (Task 16).** `SPAStaticFiles` serves `index.html` for unknown non-API paths so
  deep links survive refresh, while `/api/*` misses keep the JSON envelope 404.
- **MSW deferred.** Phase 2 tests mock `fetch` directly; MSW + shared render helpers arrive in
  Phase 3 with the board/dashboard/admin suite.

## Result
<!-- Fill in on completion: frontend test count, backend test count, lint status, build status,
     and whether the Docker image build was verified here or deferred to Phase 4 CI. -->
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/implementation-checklist.md docs/superpowers/logs/2026-09-06-phase2-dev-log.md
git commit -m "docs: record Phase 2 completion and frontend dev log"
# append your session's Co-Authored-By trailer
```

- [ ] **Step 6: Push the branch**

```bash
git push -u origin claude/phase-2-frontend-plan-p8h3e5
```

Expected: the branch pushes. Retry with exponential backoff (2s, 4s, 8s, 16s) only on network errors. Do **not** open a pull request unless the user asks.

---

## Self-review

Run this checklist against the plan and the spec once, fixing inline.

**1. Spec coverage (§10 Frontend + related).**

| Spec requirement | Task |
|---|---|
| Login & accept-invitation (shared with reset) | 6 |
| Items Table/Board toggle persisted per browser | Table done (10–11); **Board is Phase 3** — the toggle ships with the board |
| Table: sortable columns | 10 |
| Table: filter bar (status, priority, group, category, owner, assignee, kind, due range) | 11 |
| Table: free-text search | 11 |
| Table: column visibility chooser | 11 |
| Table: URL-synced shareable filters | 9–10 |
| Item detail as right-side sheet | 13 |
| Item detail full-page route for deep links | 13 |
| Item detail: editable fields | 13 |
| Item detail: update timeline with compose box | 14 |
| Item detail: History tab rendering audit diffs | 15 |
| TanStack Query server state, query keys per resource | 5, 9, 12, 14, 15 |
| Forms via react-hook-form + zod mirroring backend schemas | 6, 12 |
| Generated TS client from OpenAPI | 4, 8 |
| Field-level errors inline, toasts, global error boundary, session-expiry redirect | 6, 7, 12 |
| Light/dark themes via CSS variables | 2 |
| Clean data-product aesthetic; semantic status/priority color | 2, 3 |
| Built into the same image; single container serves API + UI | 16 |
| Dashboard, Kanban board, Admin (users/vocab/import/export) | **Phase 3 (out of scope here)** |

Deliberately deferred to Phase 3 (per spec §14 phasing and the checklist): Dashboard screen, Kanban board + Table/Board toggle, Admin area (users/invitations/vocab/import/export UI), and the full component test suite for those screens. This plan delivers Phase 2 "Frontend core" exactly.

**2. Placeholder scan.** The only intentional placeholders are the router's Phase-3 route stubs (`ComingSoon`) and the `UpdatesTab`/`HistoryTab` files created in Task 13 and replaced with real code in Tasks 14–15 — each is complete, compiling code, not a TODO. No step says "add error handling"/"write tests for the above" without the actual code.

**3. Type consistency.** `apiFetch`/`apiList` and `ApiError` (Task 4) are used unchanged in every hook. `ItemFilters` (Task 9) is the single filter type across `filters.ts`, `useItems`, `ItemsPage`, and `FilterBar`. `ItemFormValues` + `itemFormSchema` (Task 12) feed both `NewItemButton` and `DetailsTab` (via `itemToFormValues`, Task 13). Query keys come only from `qk` (Task 5). Domain badge props (`status: string | null`, `priority: string | null`, `owner: string`) match the DTO fields they render.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-09-06-phase2-frontend-core.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration. REQUIRED SUB-SKILL: superpowers:subagent-driven-development.

**2. Inline Execution** — execute tasks in this session with checkpoints for review. REQUIRED SUB-SKILL: superpowers:executing-plans.

**Which approach?**

