# vtaskforge — Design Notes

Status: Ideation (started 2026-03-18)

## Problem

When working on implementation plans, we go through: design docs + diagrams, then an implementation plan refined into phases and tasks. Today there is no structured way for an LLM agent to know what's been done, what's next, or to hand off work to another session or agent. Workspace journals capture narrative but aren't machine-parseable.

## Vision

A distributed task execution system for LLM agents, backed by Postgres, communicating via web RPC and events, tightly integrated with mykb for knowledge context.

The core idea: each task is an **agent work packet** — it contains enough context (description, acceptance criteria, kb areas, files, docs) that any LLM agent can pick it up cold and execute it.

## Core Concepts

| Concept | Description |
|---------|-------------|
| Initiative | A refined implementation plan with phases and tasks. Born from design/planning collaboration. |
| Phase | Ordered grouping within an initiative. Sequential execution. |
| Task | An agent-executable work packet. Full context for cold handoff. |
| Agent | An LLM worker (local or remote) that claims and executes tasks. Roles: executor, reviewer, architect, scrum_master. |

## Hierarchy

```
Initiative(s)
 └── Phase(s)
      └── Task(s)
```

- Initiatives are standalone — no mandatory binding to external systems
- External references (mykb workspaces, Jira epics, etc.) are optional links, not structural requirements
- Artifacts (design docs) exist at both initiative and task level via the link system
- Cross-initiative dependencies are informal (text notes, not enforced)

## Decided So Far

- **Separate system from mykb** — own tool (`vtaskforge`), own storage. Not `kb initiative`.
- **Postgres** as central store — multiple agents on different machines need access.
- **Web RPC + events** for all communication — localhost or public IP makes no difference to the system. Location-agnostic from day one.
- **Pull + push task distribution** — agents claim tasks from a pool by default, but tasks can be pinned to a specific agent or require specific tags.
- **Agent matching** — three levels: open (any agent), tagged (agents matching `requires` tags), pinned (specific `assigned_to` agent). Modeled after GitLab runner tags.
- **Atomic claims** — task claiming uses atomic Postgres UPDATE with WHERE clause (status=todo + tag matching + assignment check). Two agents racing: one wins, one gets 409 Conflict.
- **Task statuses**: draft, pending_start_review, todo, doing, pending_completion_review, changes_requested, needs_attention, blocked, deferred, cancelled, done (full lifecycle).
- **Result = commit + status update** — the code is the deliverable. Agent pushes a commit or MR and marks the task done.
- **KB area linking** — tasks reference mykb knowledge areas so agents can `kb load` relevant context.
- **Tasks as agent work packets** — each task carries: title, description, acceptance criteria, linked areas, relevant files, related docs, blockers, notes.

## Entity Shapes (Draft)

### Initiative

```
Initiative:
  id: nanoid
  name: "Auth system rewrite"
  description: "Replace legacy auth middleware..."
  status: active | completed | archived
  owner: <actor_id>
  tags: ["backend", "security"]
  target_date: ISO 8601 | null

  # Review defaults (cascade to phases → tasks)
  default_needs_review_before_start: true | false
  default_needs_review_on_completion: true | false

  # Metadata
  created_at: ISO 8601
  created_by: <actor_id>

  # All references via link system (docs, jira, areas, etc.)
```

- Status is independently set, not auto-derived (except: completing the last phase auto-completes the initiative)
- Tags are freeform strings for filtering and search

### Phase

```
Phase:
  id: nanoid
  name: "Phase 1 — Core filtering"
  description: "Implement zone-based filtering across all query paths"
  initiative_id: <initiative-nanoid>
  status: pending | active | completed

  # Review defaults (override initiative, cascade to tasks. null = inherit)
  default_needs_review_before_start: true | false | null
  default_needs_review_on_completion: true | false | null

  # Metadata
  created_at: ISO 8601
  created_by: <actor_id>

  # Dependencies via link system (DAG — phases can depend on other phases)
  # No depends_on links = no dependencies (can start immediately)
```

- Phase dependencies form a **DAG** via the link system, not a linear sequence
- Multiple phases can be `active` simultaneously
- A phase becomes activatable when all its `depends_on` phase links are `completed`
- Completing the last phase auto-completes the initiative

### Task

```
Task:
  id: nanoid
  title: "Filter archived entries from kb load output"
  status: draft | pending_start_review | todo | doing | pending_completion_review | changes_requested | needs_attention | blocked | deferred | cancelled | done
  phase_id: <phase-nanoid>
  initiative_id: <initiative-nanoid>

  # Agent context (core fields on the task itself)
  description: "kb load and scorer.ts don't filter by zone..."
  acceptance_criteria: ["archived entries excluded from kb load", "tests pass"]
  notes: []

  # Review flags (null = inherit from phase → initiative)
  needs_review_before_start: true | false | null
  needs_review_on_completion: true | false | null
  review_return_to: pending_start_review | pending_completion_review | null

  # Agent assignment
  requires: ["architect", "opus"]         # tag-based matching (optional)
  assigned_to: <agent_id> | null          # pinned to specific agent (optional)
  claimed_by: <agent_id> | null           # currently claimed by
  claimed_at: ISO 8601 | null
  claim_timeout: duration | null          # null = inherit from phase/initiative (default: 30m)
  claim_expires_at: ISO 8601 | null       # set on claim, extended on heartbeat

  # All relationships are links (separate table)
  # links: depends_on, blocks, relates_to, commit, mr, area, doc, file, jira
```

### Links (Universal)

Links connect any entity (initiative, phase, or task) to other entities or external references. All stored in a single generic table.

```
Link:
  id: nanoid
  source_id: <any entity nanoid>
  target_id: <entity nanoid or external reference string>
  link_type: depends_on | blocks | relates_to | commit | mr | area | doc | file | jira
  metadata: {} (optional, type-specific data)
  created_at: ISO 8601
  created_by: <actor_id>
```

| Type | Meaning | Applies to | Execution constraint |
|------|---------|-----------|---------------------|
| `depends_on` | Source depends on target | Tasks, Phases | Source can't start until target is done/completed |
| `blocks` | Source blocks target | Tasks, Phases | Inverse of depends_on |
| `relates_to` | Informational link | All | No constraint |
| `commit` | Git commit SHA | Tasks | Deliverable tracking |
| `mr` | Merge request URL | Tasks, Initiatives | Deliverable tracking |
| `area` | mykb KB area | All | Context for agents |
| `doc` | Document reference | All | Context |
| `file` | Source file path | Tasks | Context for agents |
| `jira` | Jira issue/epic key | All | External tracking |

Review flag cascade precedence: task (explicit) > phase default > initiative default.

## Open Questions

- **Hooks/automation**: How do status updates get triggered? Explicit commands, hooks, or automatic detection?
- **Agent capabilities/matching**: How to route the right task to the right agent type.
- **Concurrency**: What happens when two agents try to claim the same task.
- **Nesting depth**: Phase > Task is confirmed. Do tasks need subtasks?
- **Jira integration**: At initiative level? Optional link via link system? TBD.
- **Postgres hosting**: Local for now, production hosting decided later.

## UI Architecture

Both human and agent consumers share the same API layer. UI clients are thin — no business logic, just rendering and event subscription.

```
Postgres ← API Server (RPC + Events) → Terminal UI (Python CLI)
                                      → Web UI (SPA)
                                      → Agent clients
```

### Two Primary Views

#### DAG View (Pipeline Graph)

Primary view for understanding an initiative's execution plan. Inspired by GitLab's pipeline graph visualization.

- Phases rendered as clusters/groups of nodes
- Tasks as nodes within phases, connected by dependency arrows
- Color-coded by status (green=done, blue=doing, yellow=review, red=needs_attention, grey=todo)
- Dependency arrows show execution flow across tasks and phases
- Active tasks visually highlighted (animation/pulse)

**Click a task node → Modal view:**
- Full task details (description, acceptance criteria, notes)
- Event timeline (status history)
- Linked context (areas, files, docs, commits, MRs)
- Dependency graph (what it waits on, what waits on it)
- Context-sensitive action buttons:

| Task status | Available actions |
|---|---|
| `draft` | Edit fields, submit for review, chat with architect agent |
| `pending_start_review` | Approve, reject, request changes |
| `todo` | Assign to agent, edit, block |
| `doing` | View progress, block |
| `pending_completion_review` | Review deliverable, approve, reject, request changes |
| `needs_attention` | Triage, rewrite, reassign, create prerequisite task |
| `blocked` | Unblock, edit block reason |
| `done` | View result, linked commits/MRs |

**Click a phase cluster → Phase detail panel:**
- Phase description, progress bar (tasks done / total)
- Dependencies on other phases
- Actions: activate manually, complete manually

#### Kanban Board

Secondary view for managing work by status. Fixed column layout (v1):

| Column | Statuses | Visual |
|---|---|---|
| **Draft** | `draft` | Grey cards |
| **Review** | `pending_start_review`, `pending_completion_review` | Yellow cards, badge shows which gate |
| **Ready** | `todo` | Blue cards. Dependency-blocked tasks shown with "waiting on X" indicator |
| **In Progress** | `doing` | Blue cards, highlighted/animated |
| **Attention** | `changes_requested`, `needs_attention`, `blocked` | Red/orange cards, badge shows specific status |
| **Done** | `done` | Green cards |

- `deferred` and `cancelled` hidden by default, visible via toggle/filter
- Cards show: task title, assigned agent, phase, status badge, linked KB areas
- Status badge within grouped columns preserves granularity without column sprawl

#### View Toggle

Users switch between DAG view and Kanban view depending on intent:
- **DAG view** — understanding the plan, seeing dependencies, reviewing execution flow
- **Kanban view** — managing current work, focusing on status and throughput

### Decided

- **Two UI targets**: Terminal UI and Web UI, both consuming the same RPC API and event stream
- **Terminal UI**: Textual or Click/Typer (Python) — same language as the API server
- **Web UI**: SPA (framework TBD) — same API, same events, richer interaction
- **Real-time updates**: Both UIs subscribe to the event stream (SSE/WebSocket) — board updates live as agents claim and complete tasks
- **Thin UI layer**: No business logic in UI clients. All state management and validation lives in the API server.

### Human Interaction with Tasks

Tasks aren't just for agents — humans need to refine, review, and approve them.

#### Task Editing

- **Web UI**: Click a task to open a detail view. Edit all fields inline — title, description, acceptance criteria, files, areas, docs. Changes go through the same RPC API.
- **Terminal UI**: Different flow — likely CLI commands (`vtf task edit <id>`) or open in `$EDITOR`. Not a chat interface, but full editing capability.

#### Agent-Assisted Refinement (Web UI)

Click a task → open a chat panel with a specialist agent (architect, debugger, tester). The conversation refines the task in place — the agent updates acceptance criteria, adds files, clarifies scope as you discuss. The chat is the tool, the task update is the output.

Agent selection can be suggested based on task nature but human always overrides.

#### Task Approval Flow

Tasks have a **review mode** that controls whether they can be picked up by executing agents:

| Mode | Behavior |
|------|----------|
| `auto_approved` | Task is immediately available for agents to claim when status is `todo` |
| `needs_review` | Task stays in a `pending_review` state until a human approves it |

This gives humans control over the pipeline — high-confidence tasks flow automatically, while complex or risky tasks wait for human eyes. The review mode can be set per-task or as a default at the initiative/phase level.

#### Review System Design (SOLID / Pluggable)

The review system is designed behind interfaces so the mechanism is extensible without touching the core task state machine.

**Core interfaces:**

- **ReviewPolicy** — given a task and a transition (e.g., `todo→doing`, `doing→done`), decides whether review is required. Default implementation checks task-level setting, falls back to phase-level, then initiative-level default. Cascading precedence: task > phase > initiative.
- **Reviewer** — resolves who can approve. Default: any authenticated human. Future: role-based, team-based, quorum, automated quality gates.
- **ReviewDecision** — approve, reject (with reason), or request changes. Decisions are recorded with timestamp, reviewer identity, and reviewer type (human/agent) for audit history.

**Two independent review gates:**

| Flag | When | Purpose |
|------|------|---------|
| `needs_review_before_start` | Before task enters `todo` pool | Validate task quality, scope, and readiness |
| `needs_review_on_completion` | After agent marks `doing→done` | Verify deliverable meets acceptance criteria |

Both flags are independently settable per task, with cascading defaults (task > phase > initiative).

**State Machine:**

Valid transitions enforced by the API server:

```
draft ──→ pending_start_review       (needs_review_before_start = true)
draft ──→ todo                       (needs_review_before_start = false)

pending_start_review ──→ todo                  (approved)
pending_start_review ──→ changes_requested     (rejected, sets review_return_to)

todo ──→ doing                       (claimed by agent)
todo ──→ blocked                     (external dependency)

doing ──→ pending_completion_review  (needs_review_on_completion = true)
doing ──→ done                       (needs_review_on_completion = false)
doing ──→ needs_attention            (agent gave up)
doing ──→ blocked                    (external dependency discovered)

pending_completion_review ──→ done                  (approved)
pending_completion_review ──→ changes_requested     (rejected, sets review_return_to)

changes_requested ──→ review_return_to value        (resubmitted — routed by field)
changes_requested ──→ draft                         (needs major rework)

needs_attention ──→ draft            (needs rewrite)
needs_attention ──→ todo             (triaged, back to pool)
needs_attention ──→ cancelled        (not worth pursuing)

blocked ──→ todo                     (unblocked, back to pool)
blocked ──→ doing                    (unblocked, same agent continues)

deferred ──→ todo                    (reactivated)

Any non-terminal ──→ cancelled       (cancel from any state)
Any non-terminal ──→ deferred        (defer from any state)

done                                 (terminal — no transitions out)
cancelled                            (terminal — no transitions out)
```

**`changes_requested` routing:** The `review_return_to` field on the task stores which review gate triggered the rejection (`pending_start_review` or `pending_completion_review`). On resubmit, the task returns to that gate automatically. Field is only meaningful when status is `changes_requested`.

- Enables queries like "show me all tasks that needed rework" without structural complexity

**Reviewer types:**

V1: any authenticated human. Future: the Reviewer interface supports human reviewers, expert agents (architect agent reviewing task definitions, testing agent verifying acceptance criteria), or composite reviewers (agent review + human sign-off). ReviewDecision records reviewer type for audit and for policies like "agent-reviewed tasks still need human sign-off".

**V1 implementation:** ReviewPolicy reads the two flags, Reviewer is "any human", ReviewDecision is approve/reject/changes_requested. Interfaces are in place for future extension.

#### Task Status Flow

See Review System Design below for the full status flow diagram.

### Alternatives Considered

- **Ink** (React for CLI, Node/TS) — polished TUI but different language from the API server
- **Bubbletea** (Go) — performant but different language stack
- **Blessed/neo-blessed** (Node) — older, less maintained

## Design Topics to Explore

The following topics have been identified but not yet designed. Each should be discussed and resolved before or during implementation.

### 1. ~~Intake — Plan to Initiative~~ (Resolved)

**Decided: Out of scope for vtaskforge.** Intake/parsing of plan documents is a consumer concern — a Claude Code skill, an agent, or a manual process that calls the vtf API. vtaskforge provides CRUD for initiatives, phases, and tasks. How they get populated is not vtf's problem.

vtf's API surface for this:
- `vtf initiative create --name "..."`
- `vtf phase create --initiative <id> --name "..."`
- `vtf task create --phase <id> --title "..." [--description, --areas, --files, ...]`
- `vtf task update <id> [--title, --description, --areas, --files, ...]`

Tasks are rich objects built up incrementally — create with minimal fields, then enrich via update and link commands. Bulk creation supported via `--from <file.yaml>` for intake tools.

### 2. ~~Task Dependencies~~ (Resolved) → Links & Relations

Generalized into a **link system** that handles dependencies and all other relationships between entities.

**Link types:**

| Type | Meaning | Execution constraint |
|------|---------|---------------------|
| `depends_on` | Task A depends on Task B | A can't start until B is done |
| `blocks` | Task A blocks Task B | Inverse of depends_on |
| `relates_to` | Informational link | No constraint |
| `commit` | Task → git commit SHA | Deliverable tracking |
| `mr` | Task → merge request URL | Deliverable tracking |
| `area` | Task → mykb KB area | Context for agents |
| `doc` | Task → document reference | Context for agents |
| `file` | Task → source file path | Context for agents |

**CLI:**

```bash
vtf link add <source-id> --depends-on <target-id>
vtf link add <source-id> --blocks <target-id>
vtf link add <source-id> --relates-to <target-id>
vtf link add <source-id> --commit <sha>
vtf link add <source-id> --mr <url>
vtf link add <source-id> --area <kb-area>
vtf link add <source-id> --doc <path-or-url>
vtf link rm <link-id>
vtf link list <entity-id>
```

**Storage:** Generic `links` table — `source_id`, `target_id`, `link_type`, `metadata`. Extensible for new link types without schema changes.

**Execution impact:** `depends_on`/`blocks` links form a DAG within a phase. Agents can only claim tasks whose dependencies are all `done`. This unlocks parallel execution — agents grab any unblocked task rather than waiting for the whole phase.

### 3. ~~Observability / Activity Log~~ (Resolved)

**Decided: vtaskforge owns task-level observability only.** Agent session capture (turns, tool calls, tokens, health) belongs to a separate agent pool manager system.

**Task event log** — separate `task_events` table, append-only:

| Event type | Data |
|-----------|------|
| `status_changed` | from, to, timestamp, triggered_by |
| `claimed` | agent_id, timestamp |
| `review_submitted` | reviewer_id, reviewer_type, decision, reason |
| `link_added` | link_type, target, added_by |
| `link_removed` | link_type, target, removed_by |
| `field_updated` | field, old_value, new_value, updated_by |

Enables: task timeline view, cycle time metrics (draft→done), rework rate (changes_requested count), time in review.

**Agent session telemetry is out of scope** — the agent pool manager tracks session internals (turns, tool calls, tokens, container health). The two systems link via `agent_id` + `task_id`. Prior art: VFF's observe package (Source→Parser→Emitter pipeline in `vilo-forge-factory/internal/observe/`) proved this pattern at scale.

**Agent pool manager:** The leading proposal is to evolve `vf-agents` (github.com/vilosource/vf-agents) into the agent pool manager, absorbing VFF's observe pipeline. See [agent-pool-manager-PROPOSAL.md](agent-pool-manager-PROPOSAL.md) for details.

**Surfacing:** Task detail view shows the event timeline. Kanban cards show last event as a summary line.

### 4. ~~Context Budget~~ (Resolved — Out of Scope)

**Decided: Agent pool manager concern, not vtaskforge's.** vtaskforge doesn't know about agent capabilities or context windows. The pool manager (vf-agents) knows agent capacity and can decide if a task's linked context fits before assignment.

### 5. ~~Failure Handling~~ (Resolved)

**Decided: Two-layer responsibility.**

1. **vf-agents (developer)** handles execution-level failures (container crash, timeout, OOM). It retries if appropriate, and if it gives up, unassigns itself from the task with a note explaining why — just like a real developer unassigning a ticket they can't complete.

2. **vtaskforge (board)** receives the unassignment. Task moves to `needs_attention` status with the agent's failure context attached. A human or expert agent (scrum master role) triages: rewrite the task, create prerequisite tasks, reassign, or escalate.

New status: **`needs_attention`** — the executing agent gave up and needs help. Distinct from `changes_requested` (review gate outcome). See [scrum-master-agent-PROPOSAL.md](scrum-master-agent-PROPOSAL.md) for the process agent that triages these.

### 6. ~~Naming~~ (Resolved)

Named `vtaskforge`. CLI command: `vtaskforge` (alias `vtf` TBD).

## Related Documents

- [actor-model-DESIGN.md](actor-model-DESIGN.md) — Actor types, system boundary, development team model, interaction flows
- [agent-pool-manager-PROPOSAL.md](agent-pool-manager-PROPOSAL.md) — Proposal to evolve vf-agents into the agent pool manager
- [scrum-master-agent-PROPOSAL.md](scrum-master-agent-PROPOSAL.md) — Autonomous process agent for flow facilitation and triage
- [design-gaps-ANALYSIS.md](design-gaps-ANALYSIS.md) — Identified gaps in the design requiring resolution
- [gitlab-pipeline-analogy-REFERENCE.md](gitlab-pipeline-analogy-REFERENCE.md) — Mental model: vtf as CI/CD for LLM agents, inspired by GitLab pipelines
- [api-surface-DESIGN.md](api-surface-DESIGN.md) — Full REST API surface, SSE events, error model, agent liveness
- [implementation-PLAN.md](implementation-PLAN.md) — Phased implementation plan starting with project setup
- [task-breakdown-GUIDE.md](task-breakdown-GUIDE.md) — How to decompose phases into tasks with dependency DAGs

## Not Yet Decided

- API surface / RPC methods
- Event types
- Postgres schema
- Agent registration and identity
- Authentication / authorization for remote agents
- Web UI framework (React, Vue, Svelte, etc.)
