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
| Agent | An LLM worker (local or remote) that claims and executes tasks. |

## Hierarchy

```
Workspace (mykb context)
 └── Initiative(s)
      └── Phase(s)
           └── Task(s)
```

- A workspace can have multiple initiatives
- Initiatives are bound to one workspace (not shared/movable)
- Artifacts (design docs) exist at both workspace and initiative level
- Cross-initiative dependencies are informal (text notes, not enforced)

## Decided So Far

- **Separate system from mykb** — own tool (`vtaskforge`), own storage. Not `kb initiative`.
- **Postgres** as central store — multiple agents on different machines need access.
- **Web RPC + events** for all communication — localhost or public IP makes no difference to the system. Location-agnostic from day one.
- **Pull + push task distribution** — agents claim tasks from a pool by default, but tasks can be pinned to a specific agent.
- **Task statuses**: draft, pending_start_review, todo, doing, pending_completion_review, changes_requested, blocked, deferred, cancelled, done (full lifecycle).
- **Result = commit + status update** — the code is the deliverable. Agent pushes a commit or MR and marks the task done.
- **KB area linking** — tasks reference mykb knowledge areas so agents can `kb load` relevant context.
- **Tasks as agent work packets** — each task carries: title, description, acceptance criteria, linked areas, relevant files, related docs, blockers, notes.

## Task Shape (Draft)

```
Task:
  id: nanoid
  title: "Filter archived entries from kb load output"
  status: draft | pending_start_review | todo | doing | pending_completion_review | changes_requested | blocked | deferred | cancelled | done
  phase: "phase-1-zone-filtering"
  initiative: "zone-filter-fix"

  # Agent context
  description: "kb load and scorer.ts don't filter by zone..."
  acceptance_criteria: ["archived entries excluded from kb load", "tests pass"]
  areas: ["mykb"]
  files: ["src/core/db.ts", "src/extension/hooks/scorer.ts"]
  docs: ["zone-filter-BUGFIX.md"]

  # Tracking
  blockers: []
  notes: []
  commits: []
```

## Open Questions

- **Intake**: How does a plan document become a structured initiative? Likely a dedicated command/process.
- **Hooks/automation**: How do status updates get triggered? Explicit commands, hooks, or automatic detection?
- **Agent capabilities/matching**: How to route the right task to the right agent type.
- **Concurrency**: What happens when two agents try to claim the same task.
- **Naming**: `tt`? Something else?
- **Nesting depth**: Phase > Task is confirmed. Do tasks need subtasks?
- **Jira integration**: At initiative level? Optional link? TBD.
- **Postgres hosting**: Local for now, production hosting decided later.

## UI Architecture

Both human and agent consumers share the same API layer. UI clients are thin — no business logic, just rendering and event subscription.

```
Postgres ← API Server (RPC + Events) → Terminal UI (Ink)
                                      → Web UI (SPA)
                                      → Agent clients
```

### Kanban Board

Primary view for initiatives — columns map to task statuses:

| Todo | Doing | Blocked | Done |

Cards show: task title, assigned agent, phase, linked KB areas. Expandable for full context.

### Decided

- **Two UI targets**: Terminal UI and Web UI, both consuming the same RPC API and event stream
- **Terminal UI**: Ink (React for CLI) — keeps the stack in TypeScript/Node, shares types and RPC client with the core tool
- **Web UI**: SPA (framework TBD) — same API, same events, richer interaction
- **Real-time updates**: Both UIs subscribe to the event stream (SSE/WebSocket) — board updates live as agents claim and complete tasks
- **Thin UI layer**: No business logic in UI clients. All state management and validation lives in the API server.

### Human Interaction with Tasks

Tasks aren't just for agents — humans need to refine, review, and approve them.

#### Task Editing

- **Web UI**: Click a task to open a detail view. Edit all fields inline — title, description, acceptance criteria, files, areas, docs. Changes go through the same RPC API.
- **Terminal UI**: Different flow — likely CLI commands (`tt task edit <id>`) or open in `$EDITOR`. Not a chat interface, but full editing capability.

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

**Flow:**

```
draft → pending_start_review → todo → doing → pending_completion_review → done
              ↓                                        ↓
        changes_requested ←──────────────────── changes_requested
              ↓                                        ↓
           (refine, resubmit)                   (fix, resubmit)
                        cancelled ←── (any state)
```

- `changes_requested` is a single status reachable from either review gate
- Which review triggered it is captured in the ReviewDecision history
- Enables queries like "show me all tasks that needed rework" without structural complexity

**Reviewer types:**

V1: any authenticated human. Future: the Reviewer interface supports human reviewers, expert agents (architect agent reviewing task definitions, testing agent verifying acceptance criteria), or composite reviewers (agent review + human sign-off). ReviewDecision records reviewer type for audit and for policies like "agent-reviewed tasks still need human sign-off".

**V1 implementation:** ReviewPolicy reads the two flags, Reviewer is "any human", ReviewDecision is approve/reject/changes_requested. Interfaces are in place for future extension.

#### Task Status Flow

See Review System Design below for the full status flow diagram.

### Alternatives Considered

- **Textual** (Python) — polished TUI but different language stack
- **Bubbletea** (Go) — performant but different stack
- **Blessed/neo-blessed** (Node) — older, less maintained than Ink

## Design Topics to Explore

The following topics have been identified but not yet designed. Each should be discussed and resolved before or during implementation.

### 1. Intake — Plan to Initiative

How does a markdown implementation plan become a structured initiative with phases and tasks? Likely an agent-assisted process: an intake agent reads the plan doc, proposes a task breakdown, and the human reviews/approves. This would be the first real user of the review system.

Key questions: What format constraints on the input plan? Is it a one-shot conversion or iterative refinement? How are existing tasks updated when the plan evolves?

### 2. Task Dependencies

Phases are sequential, but tasks within a phase are currently independent. Adding task-level dependencies (simple DAG within a phase) would unlock parallel agent execution — agents grab any unblocked task rather than waiting for the whole phase to complete.

Key questions: Simple "depends_on" list or full DAG? Cross-phase dependencies? How does this affect the kanban view (blocked-by vs blocked status)?

### 3. Observability / Activity Log

A timeline per task capturing operational events: claimed by agent X at 14:00, blocked at 14:02, unblocked at 14:15, completed at 14:30. Different from review history — this is operational telemetry for understanding bottlenecks and agent performance.

Key questions: Stored on the task or in a separate events table? What events are captured? Should the kanban board show a timeline view?

### 4. Context Budget

Tasks link to KB areas, files, and docs, but LLM agents have context limits. The task shape could include an estimated context size so the system can warn "this task's context exceeds agent X's capacity" before assignment.

Key questions: How to estimate context size? Static (sum of linked file sizes) or dynamic (actual token count)? Should this influence agent matching?

### 5. Failure Handling

What happens when an agent fails a task? Options: retry with same agent, reassign to a different agent type, escalate to human, back to pool. A failed attempt could trigger `changes_requested` with failure context attached.

Key questions: Max retries? Automatic escalation path? How to capture failure context (logs, error messages, partial work)?

### 6. ~~Naming~~ (Resolved)

Named `vtaskforge`. CLI command: `vtaskforge` (alias `vtf` TBD).

## Not Yet Decided

- API surface / RPC methods
- Event types
- Postgres schema
- Agent registration and identity
- Authentication / authorization for remote agents
- Web UI framework (React, Vue, Svelte, etc.)
