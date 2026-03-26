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

**Phase 3: Execution (hours/days)**

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
here before they become structured workplans. Session continuity lives here —
handoffs, journal entries, "what are we working on right now." Inspired by
mykb's workspace concept (handoff, journal, notes, state tracking), but
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

### Spec artifacts

Following the spec-driven development (SDD) pattern, the origination process
produces structured artifacts:

1. **Observations** — user-perspective notes captured during product usage.
   Quick, unstructured, varying granularity. The raw input.

2. **Spec** — what needs to change and why. Consolidates related observations
   into a coherent description of the problem and desired outcome. User
   journeys, success criteria, scope boundaries.

3. **Plan** — how to implement it. Design decisions, trade-offs, technical
   approach, codebase analysis. Produced by human-agent collaboration.

4. **Tasks** — ordered implementation steps with precise specs. The plan
   decomposed into executable work units with dependencies.

These artifacts can be backed by markdown files in a git repo — versioned,
diffable, portable. vtf indexes them, links them to tasks, and makes them
queryable via MCP and visible in the web UI. The repo is the source of truth;
vtf is the access layer.

### Key principles

1. **The human collaborates with an agent inside the Project** to drive the
   origination process. vtaskforge becomes the place where this collaboration
   happens — not just the place where the output is executed.

2. **The web UI is for the human; the underlying system is for agentic
   workflow.** The UI provides visibility, review, and steering. The API/MCP
   layer provides structured access for agents to read observations, produce
   specs, generate plans, and create tasks.

3. **Spec artifacts are the bridge** between what the user observed and what
   the developer builds. They provide traceability, preserve planning context,
   and survive between sessions.

### What needs more thinking

- What is the workspace entity? New model, or extension of Project?
- How do observations relate to the existing draft task concept?
- How does theming/grouping work? Tags, manual grouping, agent-suggested?
- What does the repo-backed storage look like? One repo per project?
- How does the agent produce specs and plans? MCP tool? Conversation flow?
- What does the workspace look like in the web UI?
- How does the handoff/journal/state from mykb translate to vtf's workspace?

These questions will be explored in subsequent design sessions.
