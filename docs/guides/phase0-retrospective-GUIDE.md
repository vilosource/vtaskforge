# Phase 0 Retrospective: Service Layer Extraction

**Date:** 2026-03-24
**Milestone:** mcp-phase0 (Service Layer Extraction)
**Workplan:** MCP Server (DcKhKOd37IHFdHNmgUefm)
**Tasks:** 8 (E0 + P0.1-P0.7)
**Reworks:** 0
**Test growth:** 801 → 857 backend, 206 CLI unchanged

## Results

All 7 service extraction tasks completed with zero reworks. Every executor delivered passing code on the first attempt. Every judge confirmed with PASS.

| Task | What | Tests Added | Judge Notes |
|------|------|-------------|-------------|
| E0 | Environment setup | 0 (migration fix) | Found missing migration for event_type field |
| P0.1 | EventService | 3 | Noted celery_tasks.py now silent on failure (behavioral nuance) |
| P0.2 | Dependency resolution | 10 | Claimable query tightened (correctness improvement) |
| P0.5 | ReviewService | 5 | Noted validation order change (serializer before status check) |
| P0.6 | Celery fix | 2 | Now produces two events per expiry (status_changed + claim_expired) |
| P0.3 | Claim logic | 8 | Noted duplicate DEFAULT_CLAIM_TIMEOUT_MINUTES constant |
| P0.4 | Find claimable | 5 | Minor type hint inaccuracy (returns QuerySet, declared list) |
| P0.7 | Enrichment helpers | 23 | Parametrized tests across all 11 statuses |

## What Worked

### The simulation protocol works
The executor→judge loop ran cleanly for all 8 tasks. Zero human intervention needed. The process:
1. Supervisor claims, creates branch, dispatches executor
2. Executor orients (reads CLAUDE.md), implements, tests, commits
3. Supervisor dispatches judge with spec + branch + baseline + executor report
4. Judge runs tests independently, reviews code, produces verdict
5. Supervisor merges on PASS

### Environment task (E0) was essential
E0 caught a missing migration that would have caused failures in P0.1. Without E0, we would have dispatched an executor into a broken environment and wasted a cycle debugging infrastructure vs code issues.

### Task specs were sufficient
Executors implemented from specs alone — no clarification needed. The specs contained enough detail (files, approach, constraints, references, acceptance criteria, test commands) for cold execution.

### Judges caught real issues
Even with PASS verdicts, judges identified:
- Behavioral nuances (celery silent failure change)
- Minor code quality issues (duplicate constants, type hint inaccuracies)
- Design tradeoffs (double task fetch in ReviewService)
These were all non-blocking but valuable observations for future work.

### Test count as progress indicator
Watching the baseline grow (801 → 857) provided a clear signal that each task was adding value without regressions.

## What Didn't Work

### vtf task lifecycle confusion
`vtf task complete` with `judge: true` moves to `pending_completion_review`, not `done`. The supervisor must approve via the review API. This wasn't obvious and caused a blocker when P0.5 couldn't be claimed because its dependency (P0.1) was still in `pending_completion_review`.

**Fix:** The supervisor must approve completed tasks through the review endpoint after the judge passes. This should be part of the standard merge flow, not discovered mid-execution.

### vafi executor auto-claiming prod tasks
The vafi dev executor was configured with `VF_VTF_API_URL=http://vtf-api.vtf-prod.svc.cluster.local:8000` — pointing at prod instead of dev. It auto-claimed P0.1 and P0.2 before we could start, causing them to go to `needs_attention` when claims expired.

**Fix:** Scaled executor to 0, patched URL to vtf-dev. Agent marked offline.

### Kubeconfig pointed at wrong cluster
Default kubeconfig (~/.kube/config) pointed at Azure AKS, not the Fuji k3s cluster where vtf is deployed. Every kubectl command needed `KUBECONFIG=~/.kube/vafi-dev.yaml`.

**Fix:** Replaced default config with Fuji cluster config.

### First attempt skipped the environment task
The initial P0.1 attempt was dispatched without establishing a baseline. The executor reported "27 pre-existing failures" which couldn't be verified. The executor's work was also incomplete (diagnostics showed unused imports).

**Fix:** Added E0 as mandatory first task. Established the environment task pattern for all future workplans.

### Pyright diagnostics are noise
Every task triggered Pyright warnings for Django imports that can't be resolved outside Docker. These are pre-existing and not caused by the executor's changes. They create visual noise during the simulation.

**Not fixed:** This is a tooling issue, not a process issue. Could be addressed by configuring Pyright with a Django plugin or stub files, but that's outside scope.

## Process Discoveries

### The supervisor does not do work
Early in the session, the process had the supervisor running tests ("Step 7: Run Test Gate — Supervisor Responsibility"). This was wrong. The supervisor orchestrates — the judge verifies. If something needs running, dispatch an agent.

### The environment is the developer's responsibility
The controller/supervisor provisions the environment. Agents work within it. The project must declare what it needs (via CLAUDE.md and test commands in specs). This maps to vafi where the controller is the automated developer.

### Task specs encode environment changes
If a task changes dependencies, the spec includes the rebuild step. If a task adds a migration, the spec includes the migrate step. The controller just dispatches — all intelligence is in the specs and agent definitions.

### Subagents don't auto-load CLAUDE.md
Verified by spike: Claude Code subagents do NOT read the repo's CLAUDE.md automatically. The agent definitions must include "Step 0: Orient yourself — read CLAUDE.md." In vafi (full Claude Code sessions), CLAUDE.md is auto-loaded.

### Worktree isolation doesn't work for subagents
The `isolation: "worktree"` parameter on the Agent tool did not create actual isolation — commits went to the main checkout. Branch-based isolation (supervisor creates branch, executor works on it) is the working approach.

## Improvements for Phase 1

1. **Automate the review approval** — after judge PASS + merge, automatically approve via review API in the same command chain
2. **Track baseline in vtf** — store the current test count somewhere persistent so it doesn't need to be passed manually to each judge
3. **Consider parallel execution** — P0.1 and P0.2 had no dependencies on each other and could have run simultaneously. Phase 1 may have similar opportunities.
4. **Monitor for Docker image staleness** — P1.1 changes requirements.txt, requiring a Docker rebuild. The spec must include this step.
5. **Include ALL test suites in task specs** — Phase 0 only ran backend tests (`docker compose exec api pytest`). CLI tests (`cd cli && pytest`) were not in `test_command.full`. They passed post-milestone but were never verified per-task. Future specs must include all suites, or the quality gate must run everything.

## Metrics

- **Tasks:** 8
- **Executor dispatches:** 8
- **Judge dispatches:** 8
- **Reworks:** 0
- **Human interventions:** 0
- **Time per task:** ~5-7 min (executor ~3min, judge ~2.5min, overhead ~1min)
- **Total new tests:** 56
- **Final baseline:** 857 backend, 206 CLI
