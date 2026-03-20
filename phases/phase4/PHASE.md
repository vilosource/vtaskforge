# Phase 4 — Web UI (React SPA)

Status: Planning (2026-03-20)

## Goal

Build a web UI as a React SPA with a Kanban board, task detail modal, and SSE live updates. Also fix API gaps needed by the UI (session auth, expand support, multi-status filter).

The web UI is the second consumer of the vtaskforge API (after the CLI). It shares the same API endpoints and event stream, validating the "thin UI layer" design principle.

## Scope

- 9 tasks total
- API fixes: session auth, expand support, multi-status filter, SSE session auth (1 task)
- Frontend scaffolding: Vite + React + TypeScript setup (1 task)
- Pages: workplan list, Kanban board (2 tasks)
- Components: task detail modal with lifecycle actions (1 task)
- Real-time: SSE live updates on the Kanban board (1 task)
- Polish: styling, responsive layout, loading/error/empty states (1 task)
- Deployment: production build in Docker, dogfood verification (1 task)
- Verification: Playwright end-to-end test suite (1 task)

## Task Index

| ID   | Name                                  | Depends On     | Judge | Isolation  | Status  |
|------|---------------------------------------|----------------|-------|------------|---------|
| 4.1  | API fixes for web UI                  | --             | Yes   | sequential | Pending |
| 4.2  | React SPA setup                       | 4.1            | Yes   | sequential | Pending |
| 4.3  | Workplan list page                    | 4.2            | No    | sequential | Pending |
| 4.4  | Kanban board view                     | 4.3            | Yes   | sequential | Pending |
| 4.5  | Task detail modal                     | 4.4            | Yes   | sequential | Pending |
| 4.6  | SSE live updates                      | 4.4            | No    | sequential | Pending |
| 4.7  | Styling and polish                    | 4.5, 4.6       | No    | sequential | Pending |
| 4.8  | Build and deploy to dogfood           | 4.7            | No    | sequential | Pending |
| 4.9  | Playwright black-box suite            | 4.8            | No    | sequential | Pending |

## DAG

```
4.1 (API fixes) → 4.2 (React setup) → 4.3 (Workplan list) → 4.4 (Kanban) → 4.5 (Task detail)
                                                                            → 4.6 (SSE updates)
                                                                               ↓          ↓
                                                                            4.7 (Styling) ← both
                                                                               ↓
                                                                            4.8 (Deploy)
                                                                               ↓
                                                                            4.9 (Playwright suite)
```

## Execution Order

Respecting dependencies and maximizing parallelism:

```
Step 1:  4.1                    — API fixes (backend only)
Step 2:  4.2                    — React SPA scaffolding
Step 3:  4.3                    — Workplan list page
Step 4:  4.4                    — Kanban board view
Step 5:  4.5 || 4.6            — parallel: task detail modal || SSE live updates
Step 6:  4.7                    — Styling and polish
Step 7:  4.8                    — Build and deploy to dogfood
Step 8:  4.9                    — Playwright black-box suite
```

Total sequential steps: 8 (vs 9 if fully sequential). One parallel opportunity at Step 5.

## Parallel Execution Notes

### Step 5: Task detail modal (4.5) || SSE live updates (4.6)

Zero file overlap:
- 4.5: `web/src/components/TaskDetail.tsx`, `web/src/components/ActionButtons.tsx`, `web/src/api/taskActions.ts`
- 4.6: `web/src/hooks/useSSE.ts`, `web/src/components/LiveIndicator.tsx`

Both modify `web/src/pages/KanbanBoard.tsx` but in different ways:
- 4.5 adds modal state and renders TaskDetail
- 4.6 adds SSE hook and renders LiveIndicator

**Shared file risk**: KanbanBoard.tsx is modified by both. Sequential is safer unless worktree isolation is used with careful merge. If running parallel, merge 4.5 first (larger change), then 4.6.

## Key Design Decisions

1. **Separate web/ directory** -- web UI lives at repo root alongside cli/ and src/. Not embedded in Django.

2. **Vite + React + TypeScript** -- modern, fast build tooling. No Create React App or Next.js.

3. **@tanstack/react-query for server state** -- handles caching, refetching, loading states. Not Redux.

4. **Session auth for browser** -- SessionAuthentication added alongside TokenAuthentication. Browser uses cookies, CLI/agents use tokens.

5. **SSE via native EventSource** -- browser EventSource handles reconnection automatically. Uses session auth (cookies).

6. **Query invalidation for SSE updates** -- v1 approach: SSE events trigger react-query cache invalidation (refetch). Simple and correct. Direct cache manipulation is a future optimization.

7. **Plain CSS** -- no CSS frameworks, no CSS-in-JS. CSS custom properties for theming. Clean and maintainable.

8. **WhiteNoise for production static serving** -- built SPA served by Django in production Docker image. No separate nginx.

## Testing Strategy

| Layer | Tool | Scope |
|-------|------|-------|
| Unit | Vitest + React Testing Library | Components in isolation, hooks, API client |
| Integration | Vitest + MSW | Components with mocked API responses |
| E2E | Playwright | Full browser tests against running dev stack |

Gate 1a (task tests): `cd web && npx vitest run` and/or `cd web && npx playwright test tests/<specific>.spec.ts`

Gate 1b (full suite): `docker compose exec api pytest tests/ && cd web && npx vitest run && cd web && npx playwright test`

## Contracts Established

| Contract | Task | Description |
|----------|------|-------------|
| session-auth | 4.1 | SessionAuthentication available alongside TokenAuthentication |
| task-expand | 4.1 | GET /v1/tasks/:id?expand=links,reviews,events returns nested data |
| web-spa-structure | 4.2 | web/ directory with Vite + React + TypeScript |
| api-client | 4.2 | Shared API client with token + session auth |
| app-routing | 4.2 | / -> workplan list, /workplans/:id -> board |
| kanban-board | 4.4 | Kanban board with 6 status columns |
| task-card | 4.4 | Task card component with title, status, claimed_by |
| task-detail-modal | 4.5 | Modal with full task details and lifecycle actions |
| task-actions | 4.5 | Action buttons call lifecycle endpoints |
| sse-live-updates | 4.6 | Board updates in real-time via SSE |
| live-indicator | 4.6 | Visual connection status indicator |
| status-colors | 4.7 | Consistent color scheme matching design doc |
| web-production-build | 4.8 | SPA built and served in production Docker image |
| web-e2e-suite | 4.9 | Playwright suite covering full lifecycle |

## Contracts Modified

| Contract | Task | Change |
|----------|------|--------|
| sse-stream | 4.1 | SSE endpoint now accepts session auth (cookies) |
