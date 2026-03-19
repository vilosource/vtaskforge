# vtaskforge — Actor Model

Status: Design (2026-03-19)

## Overview

vtaskforge models a development team where humans and AI agents collaborate on structured work. This document defines the actors, their roles, system boundaries, and interaction patterns.

## System Boundary

vtaskforge tracks two types of actors internally. All external systems interact via the RPC API and event stream.

### Internal actors (vtf knows about)

| Actor type | Identity | Role in vtf |
|---|---|---|
| **Human** | User ID, name | Creates initiatives, reviews tasks, triages, final authority |
| **Agent** | Agent ID, role label | Claims tasks, submits results, submits reviews |

Agent roles are labels, not permissions:

```
actor_id: "agent-claude-7"
actor_type: agent
actor_role: executor | reviewer | architect | scrum_master
```

### External systems (outside vtf boundary)

| System | Responsibility | Interface |
|---|---|---|
| **vf-agents** (pool manager) | Spins up executor agents, manages containers, retries, session capture | RPC API + event stream |
| **Scrum Master Agent** | Watches events, triages blockers, nudges slow reviews, generates reports | Event stream (read) + RPC API (write) |
| **Intake Tooling** | Converts plan documents into initiatives/phases/tasks | RPC API |
| **Web UI** | Human interaction — kanban board, task editing, agent chat | RPC API + event stream |
| **Terminal UI** | Human monitoring — kanban view, CLI task management | RPC API + event stream |

### Boundary diagram

```mermaid
flowchart TB
    subgraph VTF["vtaskforge System"]
        direction TB
        Human["Human\n(Product Owner)"]
        Agent["Agent\n(executor, reviewer, architect, scrum_master)"]

        subgraph Core["Core Entities"]
            Initiatives["Initiatives"]
            Phases["Phases"]
            Tasks["Tasks"]
            Links["Links"]
            Reviews["Reviews"]
            Events["Task Events"]
        end
    end

    subgraph External["External Systems"]
        PoolMgr["vf-agents\n(Pool Manager)"]
        ScrumAgent["Scrum Master Agent"]
        WebUI["Web UI"]
        TermUI["Terminal UI"]
        Intake["Intake Tooling"]
    end

    PoolMgr -->|RPC API| VTF
    ScrumAgent -->|RPC API| VTF
    WebUI -->|RPC API| VTF
    TermUI -->|RPC API| VTF
    Intake -->|RPC API| VTF

    VTF -->|Event Stream| ScrumAgent
    VTF -->|Event Stream| PoolMgr
    VTF -->|Event Stream| WebUI
    VTF -->|Event Stream| TermUI
```

## Development Team Model

The system maps directly to a real-world development team:

| Real-world role | System equivalent | What they do |
|---|---|---|
| **Product Owner** | Human | Defines initiatives, approves tasks, final say on priorities and scope |
| **Developer** | Executor Agent (via vf-agents) | Claims tasks, writes code, pushes commits, reports results |
| **Tech Lead / Senior Dev** | Reviewer Agent | Reviews task definitions (pre-start) and deliverables (post-completion) |
| **Solutions Architect** | Architect Agent | Refines tasks via chat, improves work packet quality, designs solutions |
| **Scrum Master** | Scrum Master Agent | Facilitates flow, triages blockers, monitors health, generates reports |
| **Project Board** | vtaskforge | Tracks all state, enforces rules, emits events |
| **DevOps / Workstations** | vf-agents infrastructure | Provides execution environment (containers, runtimes, credentials) |

```mermaid
flowchart TB
    subgraph Team["Development Team"]
        PO["Product Owner\n(Human)"]
        DEV["Developer\n(Executor Agent via vf-agents)"]
        TL["Tech Lead\n(Reviewer Agent)"]
        ARCH["Solutions Architect\n(Architect Agent)"]
        SM["Scrum Master\n(Scrum Master Agent)"]
        DEVOPS["DevOps\n(vf-agents infrastructure)"]
    end

    subgraph Board["Central Coordination"]
        VTF["vtaskforge\n(Project Board)"]
    end

    PO -->|Defines requirements| VTF
    PO -->|Reviews deliverables| VTF

    DEV -->|Claims work| VTF
    DEV -->|Reports progress| VTF

    TL -->|Code reviews| VTF
    TL -.->|Technical guidance| DEV

    ARCH -->|System design| VTF
    ARCH -.->|Architecture reviews| TL

    SM -->|Process facilitation| VTF
    SM -.->|Removes blockers| DEV
    SM -.->|Status reporting| PO

    DEVOPS -.->|Provides infrastructure| DEV
    DEVOPS -->|Manages agent pool| VTF

    VTF -.->|Work distribution| DEV
    VTF -.->|Status visibility| SM
    VTF -.->|Review gates| TL
```

## Actor Interaction Flow

How actors collaborate through a typical task lifecycle:

```mermaid
sequenceDiagram
    participant H as Human
    participant IT as Intake Tooling
    participant VT as vtaskforge
    participant RA as Reviewer Agent
    participant PM as vf-agents (Pool Mgr)
    participant EA as Executor Agent
    participant SM as Scrum Master Agent

    Note over H,SM: Task Lifecycle Flow

    alt Initiative Creation
        H->>VT: Create initiative/phases/tasks
    else Automated Intake
        IT->>VT: Create initiative/phases/tasks
    end

    VT->>VT: Queue tasks for review

    alt Human Review
        H->>VT: Review task at gate
    else Agent Review
        RA->>VT: Review task at gate
    end

    VT-->>PM: Task available event
    PM->>VT: Claim task
    PM->>EA: Assign task

    EA->>VT: Report progress

    alt Task Complete
        EA->>VT: Mark complete
        VT->>VT: Check needs_review_on_completion
        alt Completion Review Required
            RA->>VT: Review deliverable
        end
    else Agent Gives Up
        EA->>VT: Unassign with needs_attention
        VT-->>SM: needs_attention event
        SM->>VT: Triage and reassign
    end

    Note over SM: Continuous monitoring
    SM-->>VT: Watch event stream
    SM->>H: Nudge slow reviews
    SM->>H: Standup / metrics reports

    Note over H: Human has final authority on all decisions
```

## Actor Identity in vtf

Every action in vtf is attributed to an actor. The `task_events` table records:

```
event_id: nanoid
task_id: reference
event_type: status_changed | claimed | review_submitted | ...
actor_id: "human-jason" | "agent-claude-7"
actor_type: human | agent
actor_role: owner | executor | reviewer | architect | scrum_master
timestamp: ISO 8601
data: { ... event-specific payload }
```

This enables:
- Full audit trail — who did what, when
- Role-based queries — "show all reviews by architect agents"
- Actor performance — cycle time per executor, review turnaround per reviewer

## Design Decisions

- **vtf is role-agnostic at the permission level (v1)** — any authenticated actor can perform any action. Role-based access control is a future concern.
- **Roles are descriptive, not prescriptive** — the `actor_role` field describes what the actor is doing in context, not what it's allowed to do.
- **vtf doesn't manage agent lifecycle** — it doesn't start, stop, or health-check agents. That's vf-agents' job. vtf just records what agents do.
- **Human is always in the loop** — the system is designed so humans can intervene at any point. No fully autonomous end-to-end execution without human visibility.
