# Design: Project Hierarchy & Ad-Hoc Task Support

## Status: Draft
## Date: 2026-03-21

## Problem

vtaskforge was designed for planned, structured execution: Workplan → Phase → Task.
This model breaks for real-world usage:

- **Ad-hoc work** (bugfixes, ops tasks) has no natural home — forcing it into a
  phase feels wrong and pollutes the planned structure.
- **Multiple initiatives** on the same codebase require separate workplans that
  have no shared context (repo, conventions, backlog).
- **"Phase" implies sequential execution**, but groups of tasks often run in
  parallel. The term is misleading.
- **Agent scoping** is implicit — an agent working on vtaskforge might
  accidentally claim a task from an unrelated project.

### Motivating example

A typical session might include:
1. Fix dogfood auto-restart on boot (ops)
2. Implement phase auto-completion (planned feature)
3. Redesign the sidebar (UI improvement)
4. Debug CSS alignment (bugfix)

Items 2-4 are vtaskforge work, but only item 2 belongs in a workplan/milestone.
The rest are ad-hoc tasks with no phase, no milestone, no workplan — yet they
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
| Rename: Phase → **Milestone** | Removes sequential implication, goal-oriented |
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

### Workplan (modified)

| Field | Change |
|-------|--------|
| project | **New** — required FK to Project (CASCADE) |

All other fields unchanged.

### Milestone (renamed from Phase)

| Field | Change |
|-------|--------|
| Model name | Phase → Milestone |
| DB table | Can keep `workplans_phase` or migrate to `workplans_milestone` |
| related_name on Workplan | `phases` → `milestones` |
| related_name on Task | `phase` → `milestone` |

All other fields unchanged (name, description, workplan, status, order, etc).

### Task (modified)

| Field | Change |
|-------|--------|
| project | **New** — required FK to Project (CASCADE) |
| workplan | **Nullable** — FK to Workplan (CASCADE), default null |
| phase → milestone | **Renamed + Nullable** — FK to Milestone (CASCADE), default null |
| labels | **New** — JSONField, default [] |

### Impact on other models

| Model | Impact |
|-------|--------|
| Review | No change — FK to Task |
| Note | No change — FK to Task |
| TaskEvent | No change — FK to Task |
| Link | No change — links reference task IDs directly |
| Agent | No change — agents are project-agnostic (supervisor handles scoping) |

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
GET    /v1/projects/:id/backlog/        List tasks without workplan
```

### Renamed endpoints

```
/v1/workplans/:id/phases/     →  /v1/workplans/:id/milestones/
/v1/phases/:id/               →  /v1/milestones/:id/
/v1/phases/:id/tasks/         →  /v1/milestones/:id/tasks/
/v1/phases/:id/activate/      →  /v1/milestones/:id/activate/
/v1/phases/:id/complete/      →  /v1/milestones/:id/complete/
/v1/phases/:id/stats/         →  /v1/milestones/:id/stats/
```

### Modified endpoints

```
POST /v1/tasks/
  - project: required (was implicit via workplan)
  - workplan: optional (was required)
  - milestone: optional (was phase, required)

GET /v1/tasks/claimable?project=:id&tags=executor
  - New: project filter for scoped discovery

POST /v1/workplans/
  - project: required (new field)

POST /v1/bulk/import
  - project: required in payload
  - phase_specs → milestone_specs (renamed)
```

### Backwards compatibility

Old `phase` field names in API responses should be aliased to `milestone` during
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
vtf milestone list --workplan <id>         # was: vtf phase list (if it existed)

# Workplan scoped to project
vtf workplan create --name "v2.0" --project <id>
vtf workplan list --project <id>

# Import scoped to project
vtf import milestones/core/ --workplan <id> --project <id>
```

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
│ ● Fix phase button bug         [bugfix]  draft  │
│ ● Make dogfood auto-start      [ops]     done   │
│ ● Sidebar UX cleanup           [ui]      todo   │
└─────────────────────────────────────────────────┘
```

### Workplan detail (unchanged)

Same as today — milestones grouped by status (active/pending/completed),
click through to Kanban board per milestone.

### Kanban board

Works for both:
- Milestone board: `/projects/:pid/workplans/:wid/milestones/:mid` (structured tasks)
- Backlog board: `/projects/:pid/backlog` (ad-hoc tasks, filterable by labels)

### URL structure

```
/                                              Project list (home)
/projects/:id                                  Project dashboard
/projects/:id/workplans/:wid                   Workplan detail (milestones)
/projects/:id/workplans/:wid/milestones/:mid   Kanban board for milestone
/projects/:id/backlog                          Backlog board
/tasks/:id                                     Task detail (unchanged)
```

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

## Migration Plan

### Database migration

1. Create `Project` model
2. For each existing Workplan, create a corresponding Project (same name, tags)
3. Add `project` FK to Workplan, populate from step 2
4. Add `project` FK to Task, populate from task's workplan's project
5. Make `workplan` nullable on Task
6. Rename Phase → Milestone (model, table, FKs, related_names)
7. Make `milestone` (formerly `phase`) nullable on Task
8. Add `labels` JSONField to Task (default [])

### Code migration

1. Rename all `phase` references to `milestone` across:
   - Models, serializers, views, URLs
   - Tests and factories
   - CLI commands and client
   - Web UI components, API hooks, routes
   - Agent prompts and supervisor logic
2. Add Project app (model, serializer, views, URLs)
3. Update Task serializer/views for optional workplan/milestone
4. Update bulk import for project context
5. Update web UI: sidebar → projects, project dashboard, backlog view
6. Update CLI: project commands, default project config

### Data migration (dogfood)

```
Existing workplan "vtaskforge"    → Project "vtaskforge" + Workplan "MVP"
Existing workplan "vf-agents"     → Project "vf-agents" + Workplan "Initial Build"
Existing workplan "Platform Migr" → Project "Platform Migration" + Workplan "v2.0"
```

All existing tasks retain their workplan and milestone associations.

## What We Are NOT Building

- Project templates
- Cross-project dashboards or reports
- Recurring task templates
- Agent-to-project binding (supervisor handles scoping)
- Priority/ordering for backlog (creation date is sufficient)
- Workplan dependencies (milestone A in workplan X blocks milestone B in workplan Y)
- Time tracking

## Risks

| Risk | Mitigation |
|------|------------|
| Rename breaks all existing tests (650+) | Mechanical rename, run full suite |
| CLI breaking change | We control all CLI consumers, update atomically |
| Dogfood data migration | Script it, test on dev DB first |
| Scope creep into project management | Strict "not building" list above |
| Over-engineering the project model | Start with name + description + repo_url only |

## Implementation Order

| Step | Scope | Estimated effort |
|------|-------|-----------------|
| 1 | Phase → Milestone rename (backend + tests) | Medium |
| 2 | Phase → Milestone rename (CLI) | Small |
| 3 | Phase → Milestone rename (web UI) | Small |
| 4 | Project model + API | Medium |
| 5 | Workplan.project FK + migration | Small |
| 6 | Task.project FK + nullable workplan/milestone + labels | Medium |
| 7 | CLI: project commands + default context | Small |
| 8 | Web UI: sidebar → projects, project dashboard | Medium |
| 9 | Web UI: backlog view | Small |
| 10 | Update bulk import | Small |
| 11 | Update agent/supervisor prompts | Small |
| 12 | Dogfood data migration | Small |

Steps 1-3 can be done as a standalone rename PR. Steps 4-12 are the
project hierarchy feature.
