# The Gap Between Product Observation and Executable Work

## Problem Statement

### What vtf assumes

vtf treats every task as an executable work unit: it has a status lifecycle
(draft → todo → doing → done), can be claimed by an agent, carries a spec,
and produces a code change. The system was designed for agent simulation — an
architect writes precise specs, imports them into a workplan with milestones,
and agents execute them sequentially.

This model works well when the work is pre-planned: the architect has already
done the thinking, decomposed the problem, and produced implementation-ready
task specs.

### What actually happens

The real workflow has three distinct phases that vtf collapses into one:

**Phase 1: Observation (days/weeks)**

A user works with the product daily. Thoughts arrive incrementally:
- "The breadcrumbs on this page are broken"
- "There should be a search bar here"
- "These label pills should be colored"
- "The dashboard stats are misleading"

These get captured as draft tasks — quick, unstructured, at varying granularity.
Some are bugs, some are features, some are polish. They accumulate in the
backlog over days. This phase works fine today.

**Phase 2: Planning (one session)**

Eventually the user reviews the backlog and picks a theme to work on. A
planning session follows:

- Related items are grouped (breadcrumbs + TaskPage links + sidebar highlight
  = "navigation" theme)
- The codebase is explored to understand real scope
- Shared foundations are discovered (e.g., need a reusable Breadcrumb component,
  need a React context for project state)
- Dependencies emerge (context must exist before sidebar can consume it)
- Some backlog items merge (two items turn out to be the same fix)
- New tasks appear that nobody would have written as a backlog item (e.g.,
  "create ActiveProjectContext" — an enabler with no user-visible effect)
- An implementation order is determined based on technical dependencies

The output is a set of implementation tasks that differ from the input backlog
items in quantity, granularity, ordering, and scope.

**Phase 3: Review — spec authoring (hours)**

Draft tasks from planning have intent-level descriptions but lack the detail
an executor needs. A review pass verifies each task's assumptions against the
current codebase, authors detailed specs (file paths, interface contracts,
acceptance criteria), sets dependencies, and moves tasks to `todo`.

This is where the spec gets written. The planner decides *what* to do; the
reviewer decides *how* to specify it precisely. Spec quality at this stage
directly determines executor success rate — the breadcrumbs milestone achieved
zero rework cycles because the review pass produced detailed, codebase-verified
specs.

See: [Workplan Review Protocol](workplan-review-PROTOCOL.md) for the formalized
process. Research into structured spec formats (SHALL requirements, GIVEN/WHEN/THEN
scenarios, inspired by OpenSpec) is tracked as a backlog item.

**Phase 4: Execution (hours/days)**

Implementation tasks are worked in dependency order. Each produces code, tests,
and commits. Progress is tracked against the implementation plan, not the
original backlog items.

### The core tension

vtf has one entity (Task) serving two purposes:

1. **Requirement tracking** — capturing what needs to change (user perspective,
   "the breadcrumbs are broken")
2. **Work execution** — defining what to build (developer perspective, "create
   ActiveProjectContext")

These have different lifecycles, different granularity, and different audiences.
Forcing them into the same structure means one always suffers.

### Evidence from this session (2026-03-26)

We experienced this exact friction while working on navigation improvements:

1. **Started with 16 backlog items** — accumulated as draft tasks over previous
   days, no workplan, no grouping, varying granularity.

2. **Picked the "navigation" theme** — identified 1 backlog item ("Consistent
   breadcrumb navigation on all pages") plus related items (TaskPage links,
   sidebar, modal context).

3. **Explored the codebase** — discovered the scope was larger than any single
   backlog item described. TaskPage had broken links in breadcrumbs AND context
   cards. Sidebar needed a React context. A shared Breadcrumb component was
   needed before any page could be updated.

4. **Exploration surfaced issues not in the backlog** — sidebar not highlighting
   the active project on TaskPage and TaskDetail modal lacking hierarchy context
   were discovered during codebase exploration, not captured as backlog items.
   The planning session produced new requirements.

5. **5 backlog-style tasks became 8 implementation steps** — some steps
   (ActiveProjectContext, Breadcrumb component) don't map to any backlog item.
   Some steps solve multiple backlog items at once. The mapping is many-to-many,
   not 1:1.

6. **Cancelled the original backlog item** — losing the connection between the
   user's observation and the work being done.

### What breaks if we don't improve

Projecting the current workflow forward over the coming weeks:

**Backlog grows without structure.** 20-30 more observations accumulate as
draft tasks. Some overlap, some are duplicates phrased differently. No way to
see which items relate to each other or which themes are forming.

**Every planning session repeats the same ceremony.** Cancel old backlog items,
create new implementation tasks, lose the connection between user need and
developer work. The manual overhead is the same whether the theme has 3 items
or 15.

**Backlog count becomes meaningless.** "16 draft tasks" doesn't mean 16 units
of work. Some will merge, some will split, some will spawn enabler tasks. The
number tells you nothing about actual effort or value.

**"What did we ship?" becomes hard to answer.** If backlog items are cancelled
when planning starts, there's no trace connecting user needs to completed work.
If both are kept, the board is cluttered with cancelled/duplicate items alongside
real work.

**Agent executors lose product context.** An agent assigned "Create
ActiveProjectContext" has no idea why this context exists, what user problem it
solves, or what backlog items it serves. The spec explains the technical
approach but not the product motivation. When the agent faces a design choice,
it has no product context to inform the decision.

**Workplan progress doesn't map to user value.** "3 of 8 tasks done" means
nothing to someone asking "is the navigation fixed yet?" The implementation
tasks are developer work units, not user-visible deliverables.

**The planning output has no home.** Design decisions, trade-offs, and rationale
live in a markdown document disconnected from the task system. The workplan
description field is too small. The task spec is for implementation details,
not product context.

**Planning context evaporates between sessions.** If we plan today but implement
next week, the design decisions and rationale need to survive. Currently they
live in a Claude Code plan file (deleted on session clear) or a separate
markdown doc in the repo. Neither is linked to the tasks that depend on them.
An executor picking up the work days later has no access to the "why" behind
the "what."

### What this is NOT about

This analysis is specifically about the gap between observation and execution.
It is NOT about:

- **Task execution quality** — the claim → execute → review cycle works well
- **Agent simulation** — the vtf-supervisor/executor/judge pipeline is solid
  when given precise specs
- **The data model being wrong** — Projects, Workplans, Milestones, Tasks are
  the right hierarchy for execution
- **Backlog capture** — creating draft tasks as quick observations works fine

The problem is the missing middle: the transformation from "what the user
observed" to "what the developer should build."

## Solution Direction

### Where it lives

The origination process belongs inside vtaskforge, not in a separate system.
The human is already working within a Project — capturing observations in the
web UI, looking at the board, interacting via MCP. The planning process should
happen in the same place, not require switching to a different tool.

### The Project structure

The Project is currently a thin container — a name, description, and a bag of
workplans. It needs two distinct sides:

```
Project
├── Workspace (upstream — origination)
│   ├── Observations
│   ├── Planning sessions / spec artifacts
│   ├── Session context (handoff, journal, state)
│   └── Themes / groupings
└── Workplans (downstream — execution)
    ├── Milestones
    └── Tasks (with specs)
```

**Workspace** — the active working context within a Project. This is where
the human and agent collaborate on origination. Unstructured things accumulate
here before they become structured workplans. The workspace captures:

- **Session context** — handoffs, journal, state ("what are we working on")
- **Observations** — user-perspective notes captured during product usage
- **Decisions** — choices made during planning, with rationale and rejected
  alternatives (e.g., "use React context for sidebar, not useParams — because
  the sidebar is outside route params scope")
- **Gotchas** — surprises discovered during exploration that would trip up an
  executor (e.g., "milestone field is `order` not `sort_order`", "tasks
  without milestones are invisible in workplan UI")

Decisions and gotchas are not free-text journal entries — they are typed,
structured entries that can be queried and surfaced to agents during execution.
When an executor picks up a task, the workspace's decisions explain the "why"
behind the spec, and the gotchas warn about pitfalls. Inspired by mykb's
workspace concept (handoff, journal, notes, state tracking) and its knowledge
types (decisions with `why`/`rejected`, gotchas with `source`/`failed`), but
applied to the spec-driven development workflow.

**Workplans** — the output of a completed planning session. Structured,
ordered, executable. This is what already exists in vtf and works well.

The workspace feeds workplans. When a planning session concludes, its output
flows from the workspace into a new workplan with milestones and tasks. The
observations that triggered it stay in the workspace with links to the
workplan they produced — that's the traceability.

A project without an active workspace is just a bag of workplans (execution
only). A project with an active workspace is a living collaboration space
where the next workplan is taking shape.

### Where things live

The origination process splits across two storage layers:

**vtf database (project-level):**
- Observations — quick captures from web UI, MCP, or CLI. No repo context
  needed. Linked to the project.
- Workspace state — handoff, active theme, session context.
- Workplans, milestones, tasks — execution-side entities with state machines.

**`.vtf/` directory in the project's repo (code-level):**
- Spec artifacts — spec (PRD), plan, task breakdown.
- Decisions — choices made during planning, with rationale.
- Gotchas — pitfalls discovered during exploration.

The `.vtf/` directory is committed to the repo and travels with the code. Like
`.github/` is read by GitHub's platform, `.vtf/` is read by vtaskforge. Any
agent that clones the repo has immediate access to the planning context without
needing an API call.

```
.vtf/
├── specs/
│   └── navigation/
│       ├── spec.md        # what and why (PRD)
│       ├── plan.md        # how (design decisions, approach)
│       └── tasks.md       # implementation breakdown
├── decisions/
│   └── use-react-context-for-sidebar.md
└── gotchas/
    └── tasks-without-milestone-invisible.md
```

**Why this split:**
- Observations are ephemeral inputs — they arrive before any structure exists,
  from any context (web UI, mobile, conversation). They belong in the database.
- Spec artifacts are durable outputs — they describe the code, should be
  versioned with it, and need to be readable by agents at execution time
  without an API call. They belong in the repo.
- The planning session is the bridge: agent reads observations from the
  database, explores code in the repo, writes spec artifacts to `.vtf/`.

### The origination flow

Following the spec-driven development (SDD) pattern, mapped to agile concepts:

**1. Capture** — observations land in vtf database.
Quick, unstructured, varying granularity. Like user stories in a product
backlog. No repo context needed.

**2. Organize** — human + agent consolidate related observations into a spec.
This is the PRD step — grouping related observations and asking "what is the
actual requirement here?" The output is `.vtf/specs/<name>/spec.md`. The
observations that fed into it are linked. In agile terms: stories grouped
into an epic with acceptance criteria.

**3. Plan** — human + agent produce the technical approach.
Design decisions, trade-offs, codebase analysis. The output is
`.vtf/specs/<name>/plan.md`. Decisions and gotchas are captured in `.vtf/`
as separate typed files. In agile terms: technical design / architecture
decision records.

**4. Transform** — agent breaks the plan into executable tasks.
The output is `.vtf/specs/<name>/tasks.md` in the repo AND a workplan with
milestones and tasks created in vtf via MCP. Each task's spec references
back to the plan for context. In agile terms: sprint backlog items broken
from the design.

**5. Trace** — the chain is preserved.
Tasks → plan → spec → observations. An executor agent reads the spec
artifacts from `.vtf/` for context. A stakeholder can trace any task back
to the user need that triggered it. When code ships, the spec artifacts
in the same repo document why.

### Key principles

1. **The human collaborates with an agent inside the Project** to drive the
   origination process. vtaskforge becomes the place where this collaboration
   happens — not just the place where the output is executed.

2. **The web UI is for the human; the underlying system is for agentic
   workflow.** The UI provides visibility, review, and steering. The API/MCP
   layer provides structured access for agents to read observations, produce
   specs, generate plans, and create tasks.

3. **Spec artifacts travel with the code.** They're committed to the repo in
   `.vtf/`, versioned alongside the code they describe. An agent cloning the
   repo has the full planning context without any external dependency.

4. **The spec (PRD) is the pivot point.** Everything before it (observations)
   is unstructured and lives in the database. Everything after it (plan,
   decisions, gotchas, task breakdown) is structured and lives in the repo.

### Prior art: mykb workspace artifacts

The mykb knowledge management system (`kb` CLI) already implements a workspace
artifact concept that closely resembles what `.vtf/` needs. The `kb wsa`
command provides:

- **Typed artifacts** — each has a type (plan, design, analysis, report, etc.)
- **Metadata** — description, tags, creation/update timestamps
- **Area links** — artifacts link to knowledge areas for context
- **Search** — full-text search across artifact content
- **CRUD** — add, list, show, update, delete, sync

Example from this session — saving the breadcrumb implementation plan:
```
kb wsa add breadcrumb-navigation-PLAN.md \
  --from ~/.claude/plans/kind-riding-otter.md \
  --type plan \
  --tags breadcrumbs,navigation \
  --areas vtaskforge
```

The `.vtf/` directory could follow a similar pattern: each artifact is a
markdown file with typed metadata (in frontmatter or a sidecar manifest),
linked to observations and tasks. The `vtf` CLI and MCP tools would provide
the same add/list/show/search operations that `kb wsa` provides today.

mykb also provides `kb work handoff` — a session continuity mechanism that
captures what you're working on and what's next, so the next session (human
or agent) can resume without ramp-up. This maps directly to workspace state
in `.vtf/workspace.yaml`. The handoff pattern solves the "planning context
evaporates between sessions" problem identified in this analysis.

This is not theoretical — we used both `kb wsa` and `kb work handoff` in
this session to persist the breadcrumb plan and session context because vtf
had no native way to store either. The mykb workspace is filling the gap
that `.vtf/` should eventually fill within the project repo.

### What needs more thinking

- How does the organize step work in practice? Agent reads observations and
  proposes a spec draft? Human curates manually? Both?
- What is the workspace entity in the database? New model, or extension of
  Project?
- How do observations relate to the existing draft task concept? Do draft
  tasks become observations, or do they coexist?
- Multi-repo projects — observations are project-level, but which repo gets
  the `.vtf/` spec artifacts?
- How does the agent know to read `.vtf/` when executing a task? Convention?
  Task spec reference? vtf CLI integration?
- What does multi-session planning look like? Workspace state tracks
  "currently planning: navigation" across sessions?
- What MCP tools are needed for the origination flow?
- What does this look like in the web UI when we build it?

These questions will be explored in subsequent design sessions.
