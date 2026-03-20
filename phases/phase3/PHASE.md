# Phase 3 — Polish, Fixes, Operational Features

Status: Planning (2026-03-20)

## Goal

Polish the system, fix known issues, and add operational features (pagination, SSE, real stats). This phase serves a dual purpose:

1. **Feature delivery**: fix bugs and add features needed for real usage
2. **Pipeline validation**: execute entirely through vtaskforge (dogfooding), validating the standardized agent pipeline described in simulation-gap-ANALYSIS.md

Phase 3 is the first end-to-end test of the integrated supervisor/executor/judge agent pipeline. The feature work is secondary to validating that the process works with standardized agents reading YAML specs, not hand-crafted prompts.

## Scope

- 7 tasks total
- Bug fixes: unclaim state machine gap, claim tag lookup from DB (2 tasks)
- Feature: real stats on workplan/phase endpoints (1 task)
- Feature: cursor pagination on all list endpoints (1 task)
- Feature: SSE event stream (1 task)
- CLI: events and stats commands (1 task)
- Verification: black-box test suite (1 task)

## Task Index

| ID   | Name                                  | Depends On     | Judge | Isolation  | Status  |
|------|---------------------------------------|----------------|-------|------------|---------|
| 3.1  | Fix unclaim state machine gap         | --             | No    | sequential | Pending |
| 3.2  | Fix claim tag lookup from DB          | --             | No    | sequential | Pending |
| 3.3  | Workplan and phase stats (real counts)| --             | No    | sequential | Pending |
| 3.4  | Cursor pagination on list endpoints   | 3.1, 3.2, 3.3 | Yes   | sequential | Pending |
| 3.5  | SSE event stream                      | 3.1, 3.2, 3.3 | Yes   | sequential | Pending |
| 3.6  | CLI -- events and stats commands      | 3.3, 3.5       | No    | sequential | Pending |
| 3.7  | Black-box test suite                  | 3.6            | No    | sequential | Pending |

## DAG

```
3.1 (unclaim fix) ──┐
3.2 (tag lookup)  ──┼──> 3.4 (pagination) ──┐
3.3 (stats)       ──┘    3.5 (SSE)        ──┼──> 3.6 (CLI events/stats) ──> 3.7 (black-box)
                                             └
```

## Execution Order

Respecting dependencies and maximizing parallelism:

```
Step 1:  3.1 || 3.2 || 3.3     — parallel, three independent fixes
Step 2:  3.4 || 3.5             — parallel, pagination vs SSE
Step 3:  3.6                    — sequential, needs stats + SSE
Step 4:  3.7                    — sequential, verification
```

Total sequential steps: 4 (vs 7 if fully sequential).

## Parallel Execution Notes

### Step 1: Three independent fixes (3.1, 3.2, 3.3)

Zero file overlap:
- 3.1: `src/tasks/state_machine.py`, `src/tasks/views.py` (unclaim action only)
- 3.2: `src/tasks/views.py` (claim + claimable actions only)
- 3.3: `src/workplans/views.py`

**Shared file risk**: 3.1 and 3.2 both modify `src/tasks/views.py` but in different actions (unclaim vs claim/claimable). Worktree isolation is possible but sequential is safer since both touch views.py.

### Step 2: Two independent features (3.4, 3.5)

- 3.4: `src/core/pagination.py` (new), `src/vtaskforge/settings/base.py`, all test files
- 3.5: `src/events/stream.py` (new), `src/events/urls.py`, `tests/events/test_stream.py` (new)

**Shared file risk**: 3.4 modifies settings and test files broadly. 3.5 only touches events/. Worktree isolation possible but 3.4 needs careful test updates that 3.5's new tests would also need to account for. Sequential safer.

## Key Design Decisions

1. **Polling SSE, not async** -- v1 SSE uses synchronous polling (time.sleep) with Django StreamingHttpResponse. No new dependencies. Good enough for v1 usage.

2. **DRF CursorPagination** -- uses DRF's built-in, not custom. Ordering field is created_at (most models) or timestamp (events).

3. **Agent tags from DB** -- claim endpoint now looks up agent tags from the Agent model. Request body tags serve as override for backward compatibility.

4. **Stats via ORM aggregation** -- uses Django values().annotate(Count) for efficient per-status counting.

## Contracts Established

| Contract | Task | Description |
|----------|------|-------------|
| cursor-pagination | 3.4 | All list endpoints return paginated {results, next, previous} |
| sse-stream | 3.5 | GET /v1/events/stream returns SSE-formatted event stream |
| stats-response | 3.3 | Stats endpoints return total_tasks, by_status, completed_percentage |

## Contracts Modified

| Contract | Task | Change |
|----------|------|--------|
| task-state-machine | 3.1 | doing -> todo added as valid transition |
| task-claim-endpoint | 3.2 | Claim now looks up agent tags from DB when not in request body |

## Pipeline Validation Metrics

Track these for the retrospective (see simulation-gap-ANALYSIS.md):

| Metric | Baseline (Phase 1-2) | Phase 3 Target |
|--------|---------------------|----------------|
| First-attempt success rate | 100% | Track |
| Retries needed | 0 | Track |
| Escalations (Sonnet -> Opus) | 0 | Track |
| Supervisor interventions | N/A (manual) | Track |
| Spec amendments after failure | 0 | Track |
