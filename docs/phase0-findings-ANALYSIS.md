# Phase 0 — Dry Run Findings

Status: Complete (2026-03-19)

## Overview

Phase 0 was executed as a vtaskforge simulation: 11 tasks with a dependency DAG, dispatched to subagents via cold handoff, with a supervisor (product owner + scrum master role) verifying results and tracking issues.

**Result:** All 11 tasks completed successfully. 13 tests passing, 5 Docker services running.

## Execution Stats

| Metric | Value |
|---|---|
| Total tasks | 11 |
| Sequential rounds | 8 (with 4-way parallelism in round 6) |
| Tests written | 13 |
| Agent model | Claude Opus 4.6 |
| Spec errors found by agents | 1 (celery-beat DB config) |
| Merge conflicts | 0 (lucky — no isolation) |
| Tasks requiring human intervention | 0 |

## Issues Found

### Issue #1: Unnecessary Port Exposure

**What:** docker-compose.yml exposed Postgres (5432) and Redis (6379) ports to the host. Only the api service (8000) needs host exposure — db and redis are only accessed within the Docker network.

**Impact:** Caused a port conflict with an existing local Postgres. The executing agent changed the port to 5436 as a workaround.

**Root cause:** Spec error — the docker-compose template included host port mappings that aren't needed.

**Fix:** Remove `ports` from db and redis services. Only expose api port 8000. Eliminates the entire class of port conflict issues.

**Design implication:** Task specs should be reviewed for unnecessary infrastructure exposure. Less surface = fewer environment-specific issues.

### Issue #2: Parallel Agents Without Isolation

**What:** 4 agents committed to the same branch simultaneously during the parallel round (tasks 0.6, 0.7, 0.8, 0.9). No merge conflicts occurred because they touched different files.

**Impact:** Got lucky. If two tasks had modified `settings/base.py` (which tasks 0.5 and 0.9 both did, but sequentially), there would have been a conflict.

**Root cause:** Worktree isolation wasn't available in the execution environment.

**Fix for vtaskforge:** vf-agents must give each executor agent its own git worktree or branch. The supervisor (or an automated process) merges results after verification. This is a core requirement, not a nice-to-have.

**Design implication:** The agent pool manager proposal should explicitly address git isolation as part of the execution environment setup.

### Issue #3: Spec Error — celery-beat DB Requirement

**What:** Task 0.4 spec said celery-beat doesn't need `DATABASE_URL`. Task 0.8 agent discovered `django_celery_beat.schedulers:DatabaseScheduler` requires DB access. The agent self-corrected.

**Impact:** None — the agent fixed it. But a less capable agent might have failed.

**Root cause:** Incorrect assumption in the spec. The spec author didn't trace the dependency chain: `DatabaseScheduler` → needs Django ORM → needs database.

**Fix:** Update the docker-compose spec to include `DATABASE_URL` and `db` dependency for celery-beat.

**Design implications:**
1. `needs_review_on_completion` would catch this — the reviewer sees the deviation from spec
2. Task notes (the append-only comment system) are the right place for agents to flag spec issues
3. The spec correction should flow back to the implementation plan for future reference

### Issue #4: Agent Capability vs Task Spec Detail

**What:** All agents completed without asking questions. But they were all Opus 4.6 — a high-reasoning model that can self-correct, infer intent, and fix spec errors.

**Impact:** The success rate would likely be lower with less capable models.

**Root cause:** Task specs were written at a level appropriate for high-capability agents. They specify intent, constraints, and acceptance criteria — but not step-by-step instructions.

**Analysis:** The level of detail needed in a task spec is inversely proportional to the executing agent's capability:

| Agent capability | What the spec needs | Example |
|---|---|---|
| **High** (Opus-class) | Intent + acceptance criteria + key constraints. Agent can figure out implementation details, handle edge cases, self-correct from errors. | "Create a health endpoint checking DB and Redis. Return 200/503 with JSON status." |
| **Medium** (Sonnet-class) | Specific files + implementation approach + verification commands. Agent follows the approach but may struggle with unexpected errors. | "Create src/core/views.py with a DRF APIView. Check DB via ensure_connection(). Wire at /v1/health. Verify with curl." |
| **Low** (Haiku-class) | Near-complete code snippets + exact commands. Agent mostly copies and adapts. May not recover from errors. | Full code listing for views.py, exact URL wiring code, exact curl command with expected output. |

**Design implications:**
1. The `requires` tag on tasks should indicate minimum agent capability needed
2. The task breakdown guide should have a section on calibrating spec detail to agent capability
3. The scrum master agent should consider "wrong agent level" as a triage option when a task hits `needs_attention` — the fix might be "assign to more capable agent" or "add more detail to the spec"
4. Phase 0 specs are in the Sonnet-to-Opus range. For cheaper execution, tasks like "create __init__.py files" could use Haiku with more prescriptive specs.

### Issue #5: Pyright False Positives

**What:** Every agent's work triggered Pyright errors for packages only installed inside Docker containers.

**Impact:** Zero — noise only. No agent was confused.

**Root cause:** Local IDE tooling doesn't have access to the Docker container's Python environment.

**Fix:** Not a vtaskforge concern. Local dev environment config (create a local venv with the same packages, or configure Pyright to ignore known packages).

## What Worked Well

### DAG Parallelism
4 tasks ran simultaneously after Task 0.5 completed. Total wall-clock time was significantly less than sequential execution. The dependency graph was correct — no task started before prerequisites were done.

### Cold Handoff
Every agent received only the task description from the implementation plan. No additional context was provided. All 11 completed successfully. This validates:
- The task breakdown process in the guide
- The level of detail in Phase 0 specs (for Opus-class agents)
- The "agent work packet" concept from the vtaskforge design

### Acceptance Criteria Were Verifiable
Every acceptance criterion could be checked with a concrete command (`curl`, `docker compose exec`, `pytest`). The supervisor could verify pass/fail objectively without subjective judgment.

### Task Boundaries Were Clean
No two parallel tasks modified the same file. The decomposition correctly identified independent units of work. This is the key to safe parallelism.

## Recommendations for vtaskforge Design

Based on this dry run:

1. **Git isolation is mandatory** for parallel agent execution. Add to agent pool manager requirements.

2. **Task notes must support "spec deviation" reporting.** When an agent deviates from the spec (like fixing celery-beat config), it should flag this in a structured way that the reviewer and scrum master can act on.

3. **Agent capability tags should be first-class.** The `requires` system isn't just about routing — it determines whether the task spec is detailed enough for the assigned agent.

4. **Spec detail calibration** should be part of the task breakdown guide. Add a section mapping agent capability to spec detail level.

5. **Verification should be a formal step.** In this run, the supervisor verified each task's acceptance criteria. In vtaskforge, this maps to `needs_review_on_completion`. The reviewer should have a checklist to verify, not just a subjective "looks good."

6. **Port exposure should be minimal** in Docker dev environments. Only expose what the host actually needs (the API port). Internal-only services stay internal.

7. **The scrum master agent needs "reassign to more capable agent" as a triage action** when tasks fail due to spec detail vs agent capability mismatch.
