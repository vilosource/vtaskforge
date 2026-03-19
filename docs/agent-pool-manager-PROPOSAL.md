# Agent Pool Manager — Proposal

Status: Idea (2026-03-19)

## Context

vtaskforge manages task lifecycle (initiatives, phases, tasks, reviews, events). It needs a counterpart system that manages **agent lifecycle** — claiming tasks, executing them, capturing session telemetry, and reporting results back.

## Proposal: Evolve vf-agents

Rather than building a new project from scratch, evolve **vf-agents** (`github.com/vilosource/vf-agents`) into the agent pool manager. vf-agents already has the execution layer — it needs an orchestration layer on top.

### What vf-agents already provides

| Capability | Status |
|-----------|--------|
| Runtime adapters (Claude, Gemini, Pi) | Production-ready |
| Container lifecycle (build, run, capture) | Production-ready |
| Instruction assembly (common.md → runtime-specific) | Production-ready |
| Result normalization (StandardResult) | Production-ready |
| OTEL integration | Production-ready |
| Multi-runtime support behind interfaces | Production-ready |
| Container image layering (base → toolset → runtime) | Production-ready |

### What needs to be added

| Capability | Description |
|-----------|-------------|
| Task claiming | Pull unblocked tasks from vtaskforge's pool via RPC API |
| Pool management | Multiple agents running concurrently, work distribution |
| Task context injection | Receive a work packet from vtf, materialize as agent instructions |
| Session telemetry reporting | Push turns, tokens, health events (reuse VFF observe pipeline) |
| Result reporting | Mark task done in vtf with commit/MR links |

### VFF lineage

vf-agents would also absorb the useful parts of VFF (`vilo-forge-factory`):

- **Observe pipeline** (`internal/observe/`): Source → Parser → Emitter pattern for session capture
- **Event types**: session.start, agent.turn, agent.tool_use, agent.token_usage, container.stats
- **Checkpoint persistence**: Atomic file-based offset tracking for JSONL watching

VFF's factory loop and judge/satisfaction model would NOT be carried over — those are VFF-specific concerns.

### Integration architecture

```
vtaskforge                              vf-agents (agent pool manager)
┌─────────────────────┐                ┌──────────────────────────────┐
│ Initiatives         │                │ Agent Registry               │
│ Phases              │   RPC/Events   │ Runtime Adapters             │
│ Tasks (pool)        │◄──────────────►│ Pool Manager (new)           │
│ Links & Dependencies│                │ Task Claimer (new)           │
│ Review Gates        │                │ Instruction Materializer(new)│
│ Task Event Log      │                │ Session Capture (from VFF)   │
│ Kanban UI           │                │ Container Lifecycle          │
└─────────────────────┘                └──────────────────────────────┘
```

### Flow

1. Pool manager polls vtf for unblocked `todo` tasks (or subscribes to events)
2. Task claimer claims a task → vtf records `claimed` event with agent_id
3. Instruction materializer converts the work packet (description, acceptance criteria, linked areas/files/docs) into runtime-specific instructions
4. Runtime adapter executes the agent in a container
5. Session capture watches the session JSONL, stores telemetry locally
6. On completion, result reporter marks task done in vtf with commit/MR links
7. On failure, reports failure context back to vtf

### Open questions

- How does vf-agents authenticate with vtf's RPC API?
- Does the pool manager run as a daemon or on-demand?
- How are agent capabilities matched to task requirements?
- What happens when an agent's container dies mid-task?
- Should vf-agents store session telemetry in its own Postgres, or in vtf's?
