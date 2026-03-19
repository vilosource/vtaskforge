# vtaskforge — Task Breakdown Guide

How to decompose a phase into tasks with dependencies. This process applies to any initiative in vtaskforge.

## The Process

### Step 1: Define the Phase Goal

Write a single sentence describing what "done" looks like for the phase. If you can't say it in one sentence, the phase is too big — split it.

**Example (Phase 0):**
> A Django project skeleton that boots in Docker, responds to a health endpoint, and has Celery connected.

### Step 2: Identify the Deliverables

List the concrete outputs the phase must produce. These become your completion checklist — the strict criteria that must ALL be met before the phase is declared complete.

Group them by category (infrastructure, API, testing, docs, etc.) for clarity.

**Example (Phase 0):**
- Infrastructure: 5 Docker services boot, healthchecks pass, hot reload works
- API: health endpoint responds, admin accessible, JSON error responses
- Testing: pytest passes, smoke tests cover critical paths
- Documentation: CLAUDE.md with dev commands

### Step 3: Decompose into Tasks

Break deliverables into tasks. Each task should be:

| Property | Rule |
|---|---|
| **Independent** | Can be worked on without knowledge of other tasks' implementation details |
| **Small** | Completable in a single session (1-3 hours for an agent) |
| **Testable** | Has clear acceptance criteria that can be verified |
| **Context-complete** | Description + acceptance criteria are enough for a cold handoff |

**How to find task boundaries:**
1. Start with the final deliverable and work backwards — what must exist before this can work?
2. Each "must exist before" relationship is a dependency
3. If a task touches multiple unrelated systems (e.g., database AND frontend), split it
4. If two tasks always change together, merge them

### Step 4: Define Acceptance Criteria

Every task needs acceptance criteria — the specific conditions that prove the task is done. Write them as verifiable statements:

**Good:**
- `docker compose config` validates without errors
- `GET /v1/health` returns `200` with `{"db": "ok", "redis": "ok"}`
- `pytest` passes with 4 tests, zero failures

**Bad:**
- "Docker works" (too vague)
- "Health endpoint is implemented" (not verifiable)
- "Tests are written" (doesn't say they pass)

### Step 5: Map Dependencies (Build the DAG)

For each task, ask: "What must be DONE before this task can START?"

Rules:
- Only add direct dependencies. If A→B→C, task C depends on B, not A (transitivity is implied)
- No circular dependencies
- Fewer dependencies = more parallelism = faster execution
- If a task has no dependencies, it can start immediately

**Draw the DAG:**
```
0.1 → 0.2 → 0.3 → 0.4 → 0.5 ──┬── 0.6
                                 ├── 0.7 ──┐
                                 ├── 0.8 ──┼── 0.10 ── 0.11
                                 └── 0.9   │
```

Look for parallelism — tasks at the same level with different dependencies can execute simultaneously. In the example above, 0.6, 0.7, 0.8, and 0.9 can all run in parallel after 0.5.

### Step 6: Validate

Before finalizing, check:

- [ ] **Coverage:** Do the tasks, when all completed, satisfy every item in the completion checklist?
- [ ] **No orphans:** Every deliverable in the checklist maps to at least one task
- [ ] **No hidden work:** Are there setup steps, configurations, or decisions not captured in any task?
- [ ] **Cold handoff test:** Could an agent pick up any single task with only its description, acceptance criteria, and linked context — and complete it without asking questions?
- [ ] **DAG is correct:** No circular dependencies, no missing edges, parallelism is real (parallel tasks don't actually share state)

## Task Template

Use this structure for each task:

```
#### Task X.Y: <Short title>

<1-3 sentence description of what to do>

- **Acceptance criteria:**
  - <Verifiable condition 1>
  - <Verifiable condition 2>
- **Depends on:** <task IDs, or "nothing">
- **Files:** <key files to create or modify>
- **Context:** <links to design docs, KB areas, or reference material>
```

The `Files` and `Context` fields map directly to vtaskforge's link system (`file` and `doc`/`area` link types).

## Example: Phase 0 Task Breakdown

See [implementation-PLAN.md](implementation-PLAN.md) for the full breakdown of Phase 0 into 11 tasks with a dependency DAG. This was the first application of this process.

Summary:
- **11 tasks** decomposed from the phase goal
- **Linear chain** for foundational work (scaffolding → requirements → Dockerfile → compose → Django)
- **4-way parallel** once the foundation is ready (mixins, health endpoint, celery, app stubs)
- **Convergence** for testing (needs health + celery done first)
- **Documentation last** (needs everything working to document accurately)

## Anti-Patterns

| Anti-pattern | Problem | Fix |
|---|---|---|
| **Mega-task** | "Set up the entire backend" | Split by concern: DB, API, auth, etc. |
| **Micro-task** | "Create `__init__.py`" | Merge with related work |
| **Vague criteria** | "It should work" | Specify exact commands and expected output |
| **False parallelism** | Tasks marked parallel but actually share files | Add the missing dependency edge |
| **Missing dependency** | Task assumes something exists but doesn't declare it | Walk through "what must exist before I start?" |
| **Circular dependency** | A needs B, B needs A | One of them is wrong — find the true order |
| **Gold plating** | Task adds extra features beyond the phase goal | Cut scope to match the phase goal exactly |
