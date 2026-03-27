# vtaskforge — Actor Model

Status: Design (2026-03-19)

## Overview

vtaskforge models a development team where humans and AI agents collaborate on structured work. This document defines the actors, their roles, system boundaries, and interaction patterns.

## C1 — System Context

Bird's eye view of vtaskforge and the actors/systems around it.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    HUMAN("👤 Product Owner<br/>Human")
    VTF("🏭 vtaskforge<br/>Distributed Task<br/>Execution System")
    AGENTS("🤖 vf-agents<br/>Agent Pool Manager")
    KB("🧠 mykb<br/>Knowledge Base")
    SCRUM("🎯 Scrum Master Agent<br/>Process Automation")
    WEBUI("🌐 Web UI<br/>Browser Interface")
    TUI("💻 Terminal UI<br/>CLI Interface")
    INTAKE("📝 Intake Tooling<br/>Markdown Converter")

    HUMAN -.->|"defines workplans<br/>reviews tasks"| VTF
    HUMAN -->|"manages via browser"| WEBUI
    HUMAN -->|"monitors via CLI"| TUI

    VTF <-->|"claims & executes<br/>tasks"| AGENTS
    VTF -->|"event stream<br/>monitoring"| SCRUM
    VTF <-->|"real-time updates"| WEBUI
    VTF <-->|"task data"| TUI

    AGENTS <-->|"loads context<br/>for execution"| KB
    INTAKE -->|"converts plans to<br/>structured tasks"| VTF
    SCRUM -.->|"process insights<br/>nudges"| HUMAN

    classDef person fill:#ff9ff3,stroke:#d63384,stroke-width:3px,color:#000
    classDef system fill:#ff6b6b,stroke:#ff4757,stroke-width:4px,color:#000
    classDef supporting fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef automation fill:#26de81,stroke:#2ed573,stroke-width:3px,color:#000

    class HUMAN person
    class VTF system
    class AGENTS,KB,WEBUI,TUI,INTAKE supporting
    class SCRUM automation
```

### Internal actors (vtf knows about)

| Actor type | Identity | Role in vtf |
|---|---|---|
| **Human** | User ID, name | Creates workplans, reviews tasks, triages, final authority |
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
| **Intake Tooling** | Converts plan documents into workplans/milestones/tasks | RPC API |
| **Web UI** | Human interaction — kanban board, task editing, agent chat | RPC API + event stream |
| **Terminal UI** | Human monitoring — kanban view, CLI task management | RPC API + event stream |

## C2 — Container (vtaskforge internals)

Zoom into vtaskforge showing its deployable components.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    subgraph "🏭 vtaskforge System"
        API("⚙️ API Server<br/>Django/Python<br/>Port 8000")
        DB[("🗄️ Postgres<br/>Task Storage<br/>Port 5432")]
        EVENTS("📡 Event Bus<br/>SSE/WebSocket<br/>Real-time Updates")
        WEBSPA("🎨 Web UI SPA<br/>Browser App")
    end

    HUMAN("👤 Product Owner")
    AGENTS("🤖 vf-agents<br/>Pool Manager")
    SCRUM("🎯 Scrum Master Agent")
    TUI("💻 Terminal UI")
    INTAKE("📝 Intake Tooling")

    HUMAN -->|"HTTPS"| WEBSPA
    AGENTS <-->|"RPC API"| API
    SCRUM -->|"Event Stream"| EVENTS
    TUI <-->|"API Calls"| API
    INTAKE -->|"Task Creation"| API

    API <-->|"SQL Queries"| DB
    API -->|"Publishes Events"| EVENTS
    EVENTS -->|"Live Updates"| WEBSPA

    classDef container fill:#ff6b6b,stroke:#ff4757,stroke-width:3px,color:#000
    classDef database fill:#4834d4,stroke:#3742fa,stroke-width:3px,color:#000
    classDef external fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef person fill:#ff9ff3,stroke:#d63384,stroke-width:3px,color:#000

    class API,EVENTS,WEBSPA container
    class DB database
    class AGENTS,SCRUM,TUI,INTAKE external
    class HUMAN person
```

## System Landscape

The full ecosystem — all systems and their relationships.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3"
  },
  "flowchart": {
    "nodeSpacing": 40,
    "rankSpacing": 40,
    "curve": "basis"
  }
}}%%

flowchart TB
    HUMAN("👤 Product Owner")

    subgraph "🏭 vtaskforge Core"
        VTF("🎯 vtaskforge API")
        DB[("🗄️ Postgres")]
        EVENTS("📡 Event Stream")
    end

    subgraph "🤖 Agent Ecosystem"
        POOL("🏊 vf-agents<br/>Pool Manager")
        EXEC("🔧 Executor Agents")
        REV("👨‍⚖️ Reviewer Agents")
        ARCH("🏗️ Architect Agents")
        SCRUM("🎯 Scrum Master")
    end

    subgraph "🧠 Knowledge System"
        KB("📚 mykb CLI")
        KBDATA[("💾 ~/.mykb/<br/>Knowledge Storage")]
    end

    subgraph "🖥️ User Interfaces"
        WEBUI("🌐 Web UI SPA")
        TUI("💻 Terminal UI")
    end

    subgraph "🔄 Supporting Tools"
        INTAKE("📝 Intake Tooling")
        REGISTRY("📦 ghcr.io<br/>Container Registry")
    end

    HUMAN --> WEBUI
    HUMAN --> TUI
    HUMAN -.-> VTF

    VTF <--> DB
    VTF --> EVENTS
    VTF <--> POOL
    VTF <--> INTAKE

    POOL --> REGISTRY
    POOL <--> EXEC
    POOL <--> REV
    POOL <--> ARCH

    EXEC <--> KB
    REV <--> KB
    ARCH <--> KB
    KB <--> KBDATA

    EVENTS --> SCRUM
    EVENTS --> WEBUI
    EVENTS --> TUI

    SCRUM -.-> HUMAN

    classDef person fill:#ff9ff3,stroke:#d63384,stroke-width:3px,color:#000
    classDef core fill:#ff6b6b,stroke:#ff4757,stroke-width:4px,color:#000
    classDef agent fill:#26de81,stroke:#2ed573,stroke-width:3px,color:#000
    classDef knowledge fill:#a55eea,stroke:#8854d0,stroke-width:3px,color:#000
    classDef interface fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef support fill:#ff9f43,stroke:#ff7675,stroke-width:3px,color:#000
    classDef storage fill:#4834d4,stroke:#3742fa,stroke-width:3px,color:#000

    class HUMAN person
    class VTF,EVENTS core
    class POOL,EXEC,REV,ARCH,SCRUM agent
    class KB knowledge
    class WEBUI,TUI interface
    class INTAKE,REGISTRY support
    class DB,KBDATA storage
```

## Development Team Model

The system maps directly to a real-world development team:

| Real-world role | System equivalent | What they do |
|---|---|---|
| **Product Owner** | Human | Defines workplans, approves tasks, final say on priorities and scope |
| **Developer** | Executor Agent (via vf-agents) | Claims tasks, writes code, pushes commits, reports results |
| **Tech Lead / Senior Dev** | Reviewer Agent | Reviews task definitions (pre-start) and deliverables (post-completion) |
| **Solutions Architect** | Architect Agent | Refines tasks via chat, improves work packet quality, designs solutions |
| **Scrum Master** | Scrum Master Agent | Facilitates flow, triages blockers, monitors health, generates reports |
| **Project Board** | vtaskforge | Tracks all state, enforces rules, emits events |
| **DevOps / Workstations** | vf-agents infrastructure | Provides execution environment (containers, runtimes, credentials) |

## Deployment Diagram

What runs where — infrastructure layout with network connections.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    subgraph "☁️ Cloud Infrastructure"
        subgraph "🖥️ Server Host"
            API("⚙️ vtaskforge API<br/>Django/Python<br/>:8000")
            DB[("🗄️ Postgres<br/>:5432")]
        end

        subgraph "📦 Container Registry"
            REGISTRY("🏪 ghcr.io<br/>vf-agents-*")
        end
    end

    subgraph "🏠 Agent Host"
        POOL("🏊 vf-agents binary<br/>Go CLI")
        DOCKER("🐳 Docker Runtime")
        subgraph "🤖 Agent Containers"
            EXEC("🔧 Executor")
            REV("👨‍⚖️ Reviewer")
            ARCH("🏗️ Architect")
        end
        SCRUMDAEMON("🎯 Scrum Master<br/>Daemon Process")
    end

    subgraph "💻 Developer Machine"
        TUI("💻 Terminal UI<br/>Python CLI (Click/Typer + Textual)")
        KBCLI("📚 mykb CLI")
        KBSTORE[("💾 ~/.mykb/<br/>SQLite + JSONL")]
    end

    subgraph "🌐 Browser"
        WEBUI("🎨 Web UI SPA<br/>React/TS")
    end

    API -.->|"HTTPS:443"| WEBUI
    API <-->|"TCP:8000"| TUI
    API <-->|"TCP:8000"| POOL
    API <-->|"SSE:8000"| SCRUMDAEMON
    API <-->|"TCP:5432"| DB

    POOL <-->|"Docker API"| DOCKER
    DOCKER --> EXEC
    DOCKER --> REV
    DOCKER --> ARCH
    POOL -->|"HTTPS:443"| REGISTRY

    KBCLI <--> KBSTORE
    EXEC -.->|"File I/O"| KBCLI
    REV -.->|"File I/O"| KBCLI
    ARCH -.->|"File I/O"| KBCLI

    classDef cloud fill:#87ceeb,stroke:#4682b4,stroke-width:3px,color:#000
    classDef server fill:#ff6b6b,stroke:#ff4757,stroke-width:3px,color:#000
    classDef agent fill:#26de81,stroke:#2ed573,stroke-width:3px,color:#000
    classDef dev fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef storage fill:#4834d4,stroke:#3742fa,stroke-width:3px,color:#000
    classDef browser fill:#ff9ff3,stroke:#d63384,stroke-width:3px,color:#000
    classDef registry fill:#ff9f43,stroke:#ff7675,stroke-width:3px,color:#000

    class API,DB server
    class POOL,DOCKER,EXEC,REV,ARCH,SCRUMDAEMON agent
    class TUI,KBCLI dev
    class DB,KBSTORE storage
    class WEBUI browser
    class REGISTRY registry
```

## Dynamic — Task Claiming and Execution Flow

Runtime sequence showing how a task gets claimed, executed, reviewed, and completed.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3"
  }
}}%%

sequenceDiagram
    participant VTF as 🏭 vtaskforge API
    participant POOL as 🏊 vf-agents Pool
    participant KB as 📚 mykb
    participant EXEC as 🤖 Executor Agent
    participant REV as 👨‍⚖️ Reviewer Agent

    Note over VTF,REV: 🚀 Task Execution Flow

    VTF->>+POOL: 📡 task_available event
    Note right of POOL: Pool manager receives<br/>task notification

    POOL->>+VTF: 🎯 claim_task(task_id)
    VTF-->>-POOL: ✅ task claimed

    POOL->>+VTF: 📋 get_task_details(task_id)
    VTF-->>-POOL: 📄 task spec + context

    POOL->>+KB: 🧠 load context areas
    KB-->>-POOL: 📚 knowledge base entries

    Note over POOL,EXEC: Agent Materialization
    POOL->>+EXEC: 🐳 start container with<br/>instructions + KB context
    EXEC-->>-POOL: 🟢 agent ready

    EXEC->>EXEC: 💻 execute task<br/>write code, run tests

    EXEC->>+VTF: 📤 report_completion(results)
    VTF-->>-EXEC: ✅ completion recorded

    alt 🔍 Review Required
        VTF->>+REV: 📨 review_request(task_id)
        REV->>+KB: 🧠 load review context
        KB-->>-REV: 📚 standards + patterns
        REV->>REV: 🔍 review code + results
        REV->>+VTF: ✅ approve / ❌ reject
        VTF-->>-REV: 📝 review recorded
    end

    VTF->>VTF: 🏁 mark task done
    VTF->>POOL: 📡 task_completed event

    Note over VTF,REV: 🎉 Task Complete!
```

## Actor Interaction Flow

How actors collaborate through a typical task lifecycle, including the failure path.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3"
  }
}}%%

sequenceDiagram
    participant H as 👤 Human
    participant IT as 📝 Intake Tooling
    participant VT as 🏭 vtaskforge
    participant RA as 👨‍⚖️ Reviewer Agent
    participant PM as 🏊 vf-agents (Pool Mgr)
    participant EA as 🤖 Executor Agent
    participant SM as 🎯 Scrum Master Agent

    Note over H,SM: Task Lifecycle Flow

    alt Workplan Creation
        H->>VT: Create workplan/milestones/tasks
    else Automated Intake
        IT->>VT: Create workplan/milestones/tasks
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
