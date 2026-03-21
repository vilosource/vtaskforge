# Design: Project Hierarchy & Ad-Hoc Task Support

## Status: Draft (reviewed 2026-03-21)
## Date: 2026-03-21

## Problem

vtaskforge was designed for planned, structured execution: Workplan → Milestone → Task.
This model breaks for real-world usage:

- **Ad-hoc work** (bugfixes, ops tasks) has no natural home — forcing it into a
  milestone feels wrong and pollutes the planned structure.
- **Multiple initiatives** on the same codebase require separate workplans that
  have no shared context (repo, conventions, backlog).
- **"Milestone" implies sequential execution**, but groups of tasks often run in
  parallel. The term is misleading.
- **Agent scoping** is implicit — an agent working on vtaskforge might
  accidentally claim a task from an unrelated project.

### Motivating example

A typical session might include:
1. Fix dogfood auto-restart on boot (ops)
2. Implement milestone auto-completion (planned feature)
3. Redesign the sidebar (UI improvement)
4. Debug CSS alignment (bugfix)

Items 2-4 are vtaskforge work, but only item 2 belongs in a workplan/milestone.
The rest are ad-hoc tasks with no milestone, no milestone, no workplan — yet they
clearly belong to the vtaskforge project.

## Proposal

### New hierarchy

```
Project (permanent home)
├── Workplan A (planned initiative, has end goal)
│   ├── Milestone 1 → tasks
│   └── Milestone 2 → tasks
├── Workplan B
│   └── Milestone 1 → tasks
├── Task X (backlog — no workplan, no milestone)
├── Task Y (backlog)
└── Task Z (backlog)
```

### Key changes

| Change | Detail |
|--------|--------|
| New model: **Project** | Permanent container for all work on a codebase/product |
| Rename: Milestone → **Milestone** | Removes sequential implication, goal-oriented |
| Task.workplan becomes **optional** | Tasks without a workplan sit in the project backlog |
| Task.milestone becomes **optional** | Tasks can belong to a workplan without a milestone |
| New field: **Task.labels** | Flexible tagging for ad-hoc grouping (ops, bugfix, ui) |
| New field: **Task.project** | Required — every task belongs to a project |

### Task ownership rules

```
Task:
  project:    required    (always belongs to a project)
  workplan:   optional    (null = backlog / ad-hoc)
  milestone:  optional    (null = workplan-level or backlog)
  labels:     []          (flexible cross-cutting grouping)
```

Validation:
- If `milestone` is set, `workplan` must also be set
- If `milestone` is set, it must belong to the specified `workplan`
- `workplan` must belong to the specified `project`

## Data Model

### Project (new)

| Field | Type | Notes |
|-------|------|-------|
| id | NanoID | PK |
| name | CharField(255) | Required |
| description | TextField | Optional |
| status | CharField | `active`, `archived` |
| repo_url | CharField(500) | Optional — git repo URL |
| default_branch | CharField(100) | Optional, default `main` |
| tags | JSONField | Optional metadata |
| owner | CharField(255) | Optional |
| created_by | CharField(255) | Optional |
| created_at | DateTime | Auto |
| updated_at | DateTime | Auto |

**Note:** Project does NOT carry review defaults (`default_needs_review_before_start`,
`default_needs_review_on_completion`). These stay on Workplan and Milestone only.
Review flag cascade remains: Task → Milestone → Workplan. Backlog tasks (no
milestone, no workplan) have no cascading defaults — review flags must be set
explicitly on the task itself.

### Workplan (modified)

| Field | Change |
|-------|--------|
| project | **New** — required FK to Project (CASCADE) |

All other fields unchanged.

### Milestone (renamed from Milestone)

| Field | Change |
|-------|--------|
| Model name | Milestone → Milestone |
| DB table | Can keep `workplans_milestone` or migrate to `workplans_milestone` |
| related_name on Workplan | `milestones` → `milestones` |
| related_name on Task | `milestone` → `milestone` |

All other fields unchanged (name, description, workplan, status, order, etc).

### Task (modified)

| Field | Change |
|-------|--------|
| project | **New** — required FK to Project (CASCADE) |
| workplan | **Nullable** — FK to Workplan (CASCADE), default null |
| milestone → milestone | **Renamed + Nullable** — FK to Milestone (CASCADE), default null |
| labels | **New** — JSONField, default [] |

### Impact on other models

| Model | Impact |
|-------|--------|
| Review | No change — FK to Task |
| Note | No change — FK to Task |
| TaskEvent | No change — FK to Task |
| Link | No change — links reference task IDs directly |
| Link serializer | Rename: title resolution references `milestone` → `milestone` |
| Agent | No change — agents are project-agnostic (supervisor handles scoping) |

## Affected Code Inventory

The rename touches significantly more code than it might appear. Full inventory:

| Area | Files | Occurrences | Notes |
|------|-------|-------------|-------|
| Backend (src/) | 19 | 134 | Models, views, serializers, URLs, state machine, completion, review policy |
| Tests | 21 | 947 | Highest density — factories, fixtures, assertions, test file names |
| CLI | 8 | 84 | Commands, client, import, test fixtures |
| Web UI | 15 | 153 | Components, pages, API hooks, CSS, routes |
| Docs | 18 | 333 | Design docs, guides, proposals, diagrams, INDEX |
| CLAUDE.md | 1 | 15 | Project instructions |
| **Total** | **82 files** | **~1,666** | |

The rename MUST be atomic per layer — you cannot half-rename. Each layer
(backend, CLI, web) should be one commit that renames everything and passes
all tests before moving to the next.

### Specific files requiring careful attention

| File | Why |
|------|-----|
| `src/workplans/completion.py` | New file from today — `maybe_complete_milestone()` → `maybe_complete_milestone()` |
| `src/tasks/review_policy.py` | Review flag cascade: Milestone → Workplan. Must handle nullable milestone — backlog tasks with no milestone/workplan get no cascaded defaults |
| `src/links/serializers.py` | Title resolution looks up milestone names for link display |
| `src/events/stream.py` | SSE filtering uses `milestone` references |
| `src/core/bulk_import.py` | Creates milestones nested under workplans — rename + add project support |
| `tests/factories.py` | `MilestoneFactory` → `MilestoneFactory`, used by every test file |
| `web/src/components/MilestonePipeline.tsx` | Rename to `MilestonePipeline.tsx` |
| `web/src/api/milestones.ts` | Rename to `milestones.ts`, update all hooks |
| `.claude/agents/*.md` | Supervisor and executor prompts reference "milestone" |

## API Changes

### New endpoints

```
GET    /v1/projects/                    List projects
POST   /v1/projects/                    Create project
GET    /v1/projects/:id/                Get project
PATCH  /v1/projects/:id/                Update project
DELETE /v1/projects/:id/                Delete project
GET    /v1/projects/:id/stats/          Project-level stats
GET    /v1/projects/:id/workplans/      List workplans for project
GET    /v1/projects/:id/backlog/        List tasks without workplan (paginated)
POST   /v1/projects/:id/tasks/          Create backlog task (no workplan/milestone)
```

### Project stats endpoint

`GET /v1/projects/:id/stats/` returns:

```json
{
  "project_id": "abc123",
  "total_tasks": 67,
  "backlog_tasks": 7,
  "workplan_tasks": 60,
  "by_status": {"done": 12, "doing": 8, "todo": 15, "draft": 25, ...},
  "completed_percentage": 17.9,
  "workplans": {
    "active": 1,
    "completed": 0,
    "archived": 0
  }
}
```

This counts ALL tasks in the project — both workplan tasks and backlog tasks.

### Renamed endpoints

```
/v1/workplans/:id/milestones/     →  /v1/workplans/:id/milestones/
/v1/milestones/:id/               →  /v1/milestones/:id/
/v1/milestones/:id/tasks/         →  /v1/milestones/:id/tasks/
/v1/milestones/:id/activate/      →  /v1/milestones/:id/activate/
/v1/milestones/:id/complete/      →  /v1/milestones/:id/complete/
/v1/milestones/:id/stats/         →  /v1/milestones/:id/stats/
```

### Modified endpoints

```
POST /v1/tasks/
  - project: required (was implicit via workplan)
  - workplan: optional (was required)
  - milestone: optional (was milestone, required)
  - labels: optional (new, default [])

GET /v1/tasks/?project=:id
  - New: project filter

GET /v1/tasks/claimable?project=:id&tags=executor
  - New: project filter for scoped discovery

POST /v1/workplans/
  - project: required (new field)

POST /v1/bulk/import
  - project_id or project: required in payload
  - milestones → milestones (renamed in payload)
  - New: backlog_tasks section for tasks without milestone
```

### Backwards compatibility

Old `milestone` field names in API responses should be aliased to `milestone` during
a transition period, or we do a clean break since we control all consumers
(web UI, vtf CLI, agents).

**Recommendation: clean break.** We control the CLI, web UI, and agent prompts.
No external consumers. Rename everywhere at once.

## CLI Changes

```bash
# New commands
vtf project list
vtf project create --name vtaskforge --repo git@github.com:vilosource/vtaskforge.git
vtf project show <id>

# Default project context
vtf config set project <id>

# Modified commands
vtf task create "Fix button bug" --labels bugfix,ui          # backlog task (uses default project)
vtf task create "Build auth" --workplan <id> --milestone <id> # structured task
vtf task list --project <id> --status todo
vtf task claimable --project <id> --tags executor

# Renamed
vtf milestone list --workplan <id>         # was: vtf milestone list (if it existed)

# Workplan scoped to project
vtf workplan create --name "v2.0" --project <id>
vtf workplan list --project <id>

# Import scoped to project
vtf import milestones/core/ --workplan <id> --project <id>
```

### Spec directory convention

The existing spec files live in `milestones/milestone1/`, `milestones/milestone2/`, etc.
After the rename:
- Directory: `milestones/` → `milestones/`
- Subdirectories: `milestones/core/`, `milestones/ui/`, etc.
- Milestone description: `MILESTONE.md` → `MILESTONE.md`
- Import command: `vtf import milestones/core/ --workplan <id> --project <id>`

## Web UI Changes

### Sidebar

```
Before:                          After:
WORKPLANS                        PROJECTS
● Platform Migration  11.5%      ● vtaskforge         20%
● vf-agents           0%         ● vf-agents          0%
● vtaskforge          20%        ● platform-migration  11.5%
```

Clicking a project goes to the project dashboard (not workplan detail).

### Project dashboard (new page)

```
vtaskforge
┌─────────────────────────────────────────────────┐
│ vtaskforge                                      │
│ Distributed task execution system               │
│                                                 │
│ 60 tasks  12 done  8 in progress        20%     │
│ repo: github.com/vilosource/vtaskforge          │
│ [backend] [frontend] [infra]                    │
├─────────────────────────────────────────────────┤
│ Workplans         Backlog (7)                   │
│                                                 │
│ ▾ ACTIVE                                        │
│ ┌──────────────────────────────┐                │
│ │ MVP  8 milestones  45/60     │                │
│ └──────────────────────────────┘                │
│                                                 │
│ ▸ COMPLETED (0)                                 │
├─────────────────────────────────────────────────┤
│ BACKLOG  [ops: 2] [bugfix: 3] [ui: 2]          │
│                                                 │
│ ● Fix milestone button bug     [bugfix]  draft  │
│ ● Make dogfood auto-start      [ops]     done   │
│ ● Sidebar UX cleanup           [ui]      todo   │
└─────────────────────────────────────────────────┘
```

### Workplan detail (unchanged in structure)

Same as today — milestones grouped by status (active/pending/completed),
click through to Kanban board per milestone.
Rename: "Milestones" toggle → "Milestones", MilestoneCard → MilestoneCard, etc.

### Kanban board

Works for both:
- Milestone board: `/projects/:pid/workplans/:wid/milestones/:mid` (structured tasks)
- Backlog board: `/projects/:pid/backlog` (ad-hoc tasks, filterable by labels)

**Backlog board changes:** The current `KanbanBoard` component requires `workplanId`
and optionally `milestoneId` for SSE subscriptions and task queries. The backlog board
needs a new mode:
- Query: `GET /v1/tasks/?project=:id&workplan__isnull=true` (tasks without workplan)
- SSE: `GET /v1/events/stream/?project=:id` (project-scoped events)
- No milestone/workplan context needed
- Label filter pills above the board for narrowing by label

### URL structure

```
/                                              Project list (home)
/projects/:id                                  Project dashboard
/projects/:id/workplans/:wid                   Workplan detail (milestones)
/projects/:id/workplans/:wid/milestones/:mid   Kanban board for milestone
/projects/:id/backlog                          Backlog board
/tasks/:id                                     Task detail (unchanged)
```

### Pipeline view

`MilestonePipeline.tsx` → `MilestonePipeline.tsx`. Shows milestones within a
workplan in the zigzag flow layout. No functional change beyond the rename.
The pipeline view is NOT shown on the project dashboard — it only appears
on the workplan detail page.

## SSE Event Stream Changes

The current SSE endpoint filters by `?workplan=`. Two additions needed:

```
GET /v1/events/stream/?project=:id        Project-scoped (all workplans + backlog)
GET /v1/events/stream/?workplan=:id       Workplan-scoped (unchanged)
```

The project dashboard needs project-scoped events to show live updates across
all workplans and backlog tasks. The workplan detail and milestone kanban board
continue using workplan-scoped events.

## Review Policy Changes

The review flag cascade is currently: Task → Milestone → Workplan.

With optional milestone/workplan:

| Task has | Cascade behavior |
|----------|-----------------|
| milestone + workplan | Task → Milestone → Workplan (unchanged) |
| workplan only (no milestone) | Task → Workplan (skip milestone) |
| neither (backlog task) | Task only — no cascading, use task's own flags |

`src/tasks/review_policy.py` (`get_effective_review_flags`) must handle
`task.milestone is None` and `task.workplan is None` gracefully. Currently
it always accesses `task.milestone` — this will crash on backlog tasks if not
guarded.

## Bulk Import Changes

Current payload structure:
```json
{
  "workplan_id": "abc",
  "milestones": [
    {
      "ref": "p1",
      "name": "Core API",
      "tasks": [{"ref": "t1", "title": "Build auth"}]
    }
  ],
  "links": [...]
}
```

New payload structure:
```json
{
  "project_id": "proj-abc",
  "workplan_id": "wp-abc",
  "milestones": [
    {
      "ref": "m1",
      "name": "Core API",
      "tasks": [{"ref": "t1", "title": "Build auth"}]
    }
  ],
  "backlog_tasks": [
    {"ref": "bt1", "title": "Fix button bug", "labels": ["bugfix"]}
  ],
  "links": [...]
}
```

Changes:
- `project_id` required (or `project` object to create one)
- `milestones` → `milestones`
- New `backlog_tasks` section for tasks without milestone
- Backlog tasks get `project` set, `workplan` and `milestone` null
- `ref_type_map` entries: `"milestone"` → `"milestone"`

## Task Creation Paths

With the new model there are multiple ways to create a task:

| Endpoint | Creates |
|----------|---------|
| `POST /v1/projects/:id/tasks/` | Backlog task (project only, no workplan/milestone) |
| `POST /v1/milestones/:id/tasks/` | Structured task (auto-sets milestone, workplan, project) |
| `POST /v1/tasks/` | Any task — caller provides project + optional workplan/milestone |
| `POST /v1/bulk/import` | Batch creation with milestone and/or backlog tasks |

The `POST /v1/milestones/:id/tasks/` endpoint (currently `MilestoneTasksView`)
auto-sets milestone, workplan (from milestone.workplan), and project (from
workplan.project). This is the most convenient path for structured work.

The `POST /v1/projects/:id/tasks/` endpoint is new — it auto-sets project
and leaves workplan/milestone null. This is the backlog path.

## Agent Workflow Impact

### Task discovery (scoped to project)

```
GET /v1/tasks/claimable?project=vtaskforge-id&tags=executor
```

Without project scoping, an executor meant for Go code might claim a React task
from a different project. The supervisor passes project context when dispatching.

### Supervisor workflow

```
1. Assigned to a project
2. Check for active workplans in the project
3. Process milestones within active workplans
4. Optionally process backlog tasks (ad-hoc work)
```

The supervisor already knows which project it orchestrates. No changes to the
agent model — project scoping happens at the API query level.

### Executor workflow

```
1. Receive task + project context (repo, branch)
2. Clone/navigate to correct repo
3. Read task spec
4. Execute
5. Report back
```

The project's `repo_url` and `default_branch` fields give the executor enough
context to set up its working environment without implicit assumptions.

### Task spec context

Task specs reference files, patterns, and conventions from a specific codebase.
With the project model, this context is explicit:

```json
{
  "project": {
    "name": "vtaskforge",
    "repo_url": "git@github.com:vilosource/vtaskforge.git",
    "default_branch": "develop"
  },
  "task": {
    "title": "Build auth service",
    "spec": "..."
  }
}
```

### Agent prompt updates

The following agent definitions reference "milestone" and need updating:
- `.claude/agents/vtf-supervisor.md` — dispatches by milestone
- `.claude/agents/vtf-executor.md` — receives milestone context
- `.claude/agents/vtf-judge.md` — reviews within milestone context

These are markdown prompt files, not code — the rename is textual only.

## Milestone Auto-Completion

The `maybe_complete_milestone()` function (built today in `src/workplans/completion.py`)
becomes `maybe_complete_milestone()`. Logic is unchanged:

- Guard: task has a milestone, milestone is `active`, milestone has tasks
- Query: `milestone.tasks.exclude(status__in=TERMINAL_STATUSES).exists()`
- If no non-terminal tasks remain: complete the milestone

This function is called from `perform_transition()` in `state_machine.py` when
a task reaches a terminal status. No change to the trigger — just the rename.

**Backlog tasks** (no milestone) skip this check entirely — there's nothing to
auto-complete.

## Migration Plan

### Database migration

1. Create `Project` model
2. For each existing Workplan, create a corresponding Project (same name, tags)
3. Add `project` FK to Workplan, populate from step 2
4. Add `project` FK to Task, populate from task's workplan's project
5. Make `workplan` nullable on Task
6. Rename Milestone → Milestone (model, table, FKs, related_names)
7. Make `milestone` (formerly `milestone`) nullable on Task
8. Add `labels` JSONField to Task (default [])

### Code migration

1. Rename all `milestone` references to `milestone` across:
   - Models, serializers, views, URLs
   - Tests and factories (947 occurrences — largest area)
   - CLI commands and client
   - Web UI components, API hooks, routes
   - Agent prompts and supervisor logic
   - Docs, guides, CLAUDE.md
2. Add Project app (model, serializer, views, URLs)
3. Update Task serializer/views for optional workplan/milestone
4. Update review_policy.py for nullable milestone/workplan
5. Update bulk import for project context + backlog tasks
6. Update SSE stream for project-scoped filtering
7. Update web UI: sidebar → projects, project dashboard, backlog view
8. Update KanbanBoard component for backlog mode (no workplan/milestone)
9. Update CLI: project commands, default project config
10. Update link serializer for milestone title resolution

### Data migration (dogfood)

```
Existing workplan "vtaskforge"    → Project "vtaskforge" + Workplan "MVP"
Existing workplan "vf-agents"     → Project "vf-agents" + Workplan "Initial Build"
Existing workplan "Platform Migr" → Project "Platform Migration" + Workplan "v2.0"
```

All existing tasks retain their workplan and milestone associations.

### Demo data seeding (post-deploy)

Create a demo project that showcases all the new features:

```
Project: Platform Migration
├── Workplan: v2.0
│   ├── Milestone: API Gateway (completed — all tasks done)
│   ├── Milestone: Auth Service (active — mixed statuses)
│   ├── Milestone: Data Pipeline (active — parallel with Auth)
│   ├── Milestone: Frontend SPA (pending — blocked on API)
│   └── Milestone: Load Testing (pending)
├── Backlog
│   ├── Fix CORS headers               [bugfix]     todo
│   ├── Update monitoring dashboards    [ops]        doing
│   ├── Write API docs                  [docs]       draft
│   ├── Investigate memory leak         [bugfix]     blocked
│   └── Set up staging environment      [infra]      done
```

This demonstrates:
- Parallel milestones (Auth + Data Pipeline both active)
- Sequential milestones (Frontend pending on API)
- Completed milestone
- Backlog tasks with labels at various statuses
- Project-level stats aggregating everything

## What We Are NOT Building

- Project-level review defaults (review cascade stays at Milestone → Workplan)
- Project templates
- Cross-project dashboards or reports
- Recurring task templates
- Agent-to-project binding (supervisor handles scoping)
- Priority/ordering for backlog (creation date is sufficient)
- Workplan dependencies (milestone in workplan X blocks milestone in workplan Y)
- Time tracking
- Backlog-to-milestone promotion UI (can be done via PATCH, no special UI)

## Risks

| Risk | Mitigation |
|------|------------|
| Rename blast radius (~1,666 occurrences across 82 files) | Atomic rename per layer, full test suite between each |
| Tests are the biggest risk (947 occurrences in 21 files) | Mechanical find-replace, run `pytest` after each file |
| Review policy crash on backlog tasks | Guard `task.milestone is None` and `task.workplan is None` |
| KanbanBoard assumes workplan/milestone exist | Add backlog mode with project-scoped queries |
| SSE stream doesn't support project scope | Add `?project=` filter parameter |
| CLI breaking change | We control all CLI consumers, update atomically |
| Dogfood data migration | Script it, test on dev DB first |
| Scope creep into project management | Strict "not building" list above |
| Over-engineering the project model | Start with name + description + repo_url only |

## Implementation Order

| Step | Scope | Risk | Notes |
|------|-------|------|-------|
| 1 | Milestone → Milestone rename (backend models, views, serializers, URLs) | High | Touches 19 files, 134 occurrences |
| 2 | Milestone → Milestone rename (tests + factories) | High | 21 files, 947 occurrences — must pass full suite |
| 3 | Milestone → Milestone rename (completion.py, review_policy.py, state_machine.py) | Medium | Small files but critical logic |
| 4 | Milestone → Milestone rename (CLI) | Low | 8 files, 84 occurrences |
| 5 | Milestone → Milestone rename (web UI) | Medium | 15 files, 153 occurrences, includes component renames |
| 6 | Milestone → Milestone rename (docs, CLAUDE.md, agent prompts) | Low | Textual only, no test risk |
| 7 | Project model + API + tests | Medium | New Django app, standard CRUD |
| 8 | Workplan.project FK + data migration | Low | One FK, one migration script |
| 9 | Task.project FK + nullable workplan/milestone + labels + validation | Medium | Core model change, review policy update |
| 10 | Bulk import update (project context, milestones, backlog_tasks) | Medium | Rename + new features |
| 11 | SSE stream project-scoped filtering | Low | Add query param filter |
| 12 | CLI: project commands + default context | Low | New commands, config update |
| 13 | Web UI: sidebar → projects | Medium | Component update |
| 14 | Web UI: project dashboard page | Medium | New page |
| 15 | Web UI: backlog board (KanbanBoard in project mode) | Medium | New board mode |
| 16 | Web UI: milestone rename across all components | Low | Mechanical after step 5 groundwork |
| 17 | Agent prompt updates | Low | Textual, no code |
| 18 | Dogfood deploy + data migration script | Low | Docker rebuild + migration |
| 19 | Demo data seeding + smoke test | Low | Script + Playwright verification |

Steps 1-6 are the rename (can be one PR).
Steps 7-11 are the backend project hierarchy.
Steps 12-16 are the CLI + web UI updates.
Steps 17-19 are the deployment and verification.
