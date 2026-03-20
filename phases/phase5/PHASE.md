# Phase 5 — Web UI Polish, Phase Management, Pipeline View

Status: Planning (2026-03-20)

## Goal

Polish the web UI: fix bugs, add workplan-level progress indicators, phase lifecycle management buttons, correct Kanban board titles, and a simplified DAG pipeline view for phases. Verify all changes with deployment smoke tests.

## Scope

- 6 tasks total
- Bug fix: Invalid Date in event timeline (1 task)
- Enhancement: workplan list progress columns (1 task)
- Enhancement: phase activate/complete buttons (1 task)
- Fix: Kanban board phase title (1 task)
- New feature: DAG pipeline view for phases (1 task)
- Verification: deployment smoke test + black-box (1 task)

## Task Index

| ID   | Name                                        | Depends On | Judge | Isolation  | Status  |
|------|---------------------------------------------|------------|-------|------------|---------|
| 5.1  | Fix Invalid Date in event timeline          | --         | No    | sequential | Pending |
| 5.2  | Workplan list — show phase count + progress | --         | No    | sequential | Pending |
| 5.3  | Phase status management                     | --         | No    | sequential | Pending |
| 5.4  | Kanban board title shows phase name         | --         | No    | sequential | Pending |
| 5.5  | DAG pipeline view                           | 5.3        | Yes   | sequential | Pending |
| 5.6  | Deployment smoke test + black-box           | 5.5        | No    | sequential | Pending |

## DAG

```
5.1 (Invalid Date fix) ──┐
5.2 (Workplan progress) ──┼──> 5.5 (DAG pipeline view) ──> 5.6 (Verification)
5.3 (Phase management) ──┤
5.4 (Kanban title) ───────┘
```

Note: 5.5 formally depends only on 5.3 (needs phase status buttons), but all
four small fixes (5.1-5.4) should complete before 5.5 starts since 5.5 modifies
WorkplanDetail.tsx which 5.3 also modifies.

## Execution Order

Respecting dependencies and maximizing parallelism:

```
Step 1:  5.1 || 5.2 || 5.3 || 5.4   — 4 parallel independent fixes
Step 2:  5.5                          — DAG pipeline view (new UI pattern)
Step 3:  5.6                          — Deployment smoke test + black-box
```

Total sequential steps: 3 (vs 6 if fully sequential). Four parallel opportunities at Step 1.

## Parallel Execution Notes

### Step 1: Four independent small fixes

File overlap analysis:
- 5.1: `web/src/components/EventTimeline.tsx` only
- 5.2: `web/src/pages/WorkplanList.tsx`, `web/src/api/workplans.ts`
- 5.3: `web/src/pages/WorkplanDetail.tsx`, `web/src/api/phases.ts`
- 5.4: `web/src/pages/BoardView.tsx`, `web/src/api/phases.ts`

Shared file: `web/src/api/phases.ts` is modified by both 5.3 and 5.4 (both add hooks). Merge carefully — 5.3 adds mutation hooks, 5.4 adds usePhase query hook. No conflict if appended.

## Contracts Established

| Contract | Task | Description |
|----------|------|-------------|
| phase-pipeline-view | 5.5 | Horizontal pipeline view showing phases as connected boxes with status colors and progress |

## Contracts Modified

| Contract | Task | Change |
|----------|------|--------|
| workplan-list-page | 5.2 | Added phase count, task count, and progress columns |
