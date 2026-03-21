# vtaskforge Documentation Index

## Start here

| Document | When to read |
|----------|-------------|
| [README.md](../README.md) | First time — what vtf is, quick start, CLI reference |
| [Quickstart Guide](guides/quickstart-GUIDE.md) | Getting from zero to running with your first workplan |
| [CLAUDE.md](../CLAUDE.md) | Dev setup, commands, project structure (auto-loaded by Claude Code) |

## The workflow: idea to execution

Read these in order when planning a new project:

```
1. Design your system
        ↓
2. Decompose into milestones      → Milestone Decomposition Guide
        ↓
3. Break milestones into tasks    → Task Breakdown Guide
        ↓
4. Write YAML specs + import      → Quickstart Guide
        ↓
5. Execute with agents            → Milestone Process Guide
```

| Step | Guide | What it covers |
|------|-------|---------------|
| 2 | [Milestone Decomposition Guide](guides/milestone-decomposition-GUIDE.md) | Design doc → ordered milestones. Layer identification, splitting heuristics, dependency ordering, validation checklist |
| 3 | [Task Breakdown Guide](guides/task-breakdown-GUIDE.md) | Milestone → tasks + DAG. Task sizing, acceptance criteria, dependency mapping, anti-patterns |
| 4 | [Quickstart Guide](guides/quickstart-GUIDE.md) | YAML spec format, `vtf import`, CLI workflow, web UI setup |
| 5 | [Milestone Process Guide](guides/milestone-process-GUIDE.md) | Executing milestones with agents. Role definitions (supervisor, executor, judge), verification gates, iteration process |

## Design documents

Core system design and architecture decisions.

| Document | Purpose |
|----------|---------|
| [vtaskforge Design](design/vtaskforge-DESIGN.md) | Core concepts, entity shapes, hierarchy, state machine, review system, all major decisions |
| [API Surface Design](design/api-surface-DESIGN.md) | REST endpoints, SSE events, error model, pagination, agent liveness |
| [Actor Model Design](design/actor-model-DESIGN.md) | Agent roles (executor, reviewer, architect, scrum master), interaction patterns, handoff sequences |
| [Behavioral Verification](design/behavioral-verification-DESIGN.md) | Three-layer verification: behavioral specs, judge evaluation, human review |

## Analysis and retrospectives

Learnings from building and using vtf.

| Document | Purpose |
|----------|---------|
| [Process Retrospective](design/process-retrospective-ANALYSIS.md) | What worked and what didn't across Milestones 0-4. Blast radius discovery, simulation gap, deployment testing |
| [Design Gaps Analysis](design/design-gaps-ANALYSIS.md) | Identified and resolved gaps in the original design |
| [Simulation Gap Analysis](design/simulation-gap-ANALYSIS.md) | Gap analysis for testing and simulation capabilities |

## Proposals

Future system extensions, not yet implemented.

| Document | Purpose |
|----------|---------|
| [Agent Pool Manager](proposals/agent-pool-manager-PROPOSAL.md) | Evolve vf-agents into a pool manager for agent provisioning, telemetry, container management |
| [Scrum Master Agent](proposals/scrum-master-agent-PROPOSAL.md) | Autonomous process agent for flow facilitation, triage, and blocked task resolution |

## References

Background context and mental models.

| Document | Purpose |
|----------|---------|
| [GitLab Pipeline Analogy](references/gitlab-pipeline-analogy-REFERENCE.md) | vtf as CI/CD for LLM agents — the mental model inspired by GitLab pipelines |
| [Session Handoff Guide](design/session-handoff-GUIDE.md) | How agents preserve context across session boundaries |

## Claude Code agents

Four agents in `~/.claude/agents/` automate the development workflow:

| Agent | Model | Role |
|-------|-------|------|
| `vtf-supervisor` | opus | Reads the board, dispatches executors, runs verification gates, tracks progress |
| `vtf-executor` | sonnet | Implements a single task from its spec, runs tests, commits |
| `vtf-judge` | opus | Reviews code for design compliance, architectural issues, contract violations |
| `vtf-blackbox-tester` | sonnet | End-to-end API testing via HTTP requests — no implementation knowledge |

## Milestone history

| Milestone | Status | Summary |
|----------|--------|---------|
| [Milestone 0](../milestones/milestone0/) | Complete | Django skeleton, Docker, health endpoint, Celery |
| [Milestone 1](../milestones/milestone1/) | Complete | Core models, CRUD, state machine, atomic claiming |
| [Milestone 2](../milestones/milestone2/) | Complete | Auth, claim expiry, bulk import, CLI |
| [Milestone 3](../milestones/milestone3/) | Complete | Bug fixes, stats, SSE, cursor pagination |
| [Milestone 4](../milestones/milestone4/) | Complete | React SPA, Kanban board, task detail, SSE live updates |
| [Milestone 5](../milestones/milestone5/) | Complete | UI polish, milestone management, pipeline view, Invalid Date fix |
| [Milestone 6](../milestones/milestone6/) | Complete | Task spec storage in DB, API exposure, CLI import |
| [Milestone 7](../milestones/milestone7/) | Complete | Full page task view, spec rendering, dependency chain, modal slim-down |
