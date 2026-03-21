# Story-Task Relationships Design

This document explains how User Stories relate to Tasks, Milestones, and Workplans in vtaskforge, with detailed diagrams for different scenarios.

## Overview: Dual Hierarchy

vtaskforge operates with two parallel organizational views:
- **Demand Side**: What the Product Owner wants (Stories)
- **Supply Side**: How work gets organized for execution (Tasks → Milestones → Workplans)

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3",
    "background": "#ffffff",
    "mainBkg": "#ffffff",
    "secondBkg": "#f1f2f6",
    "tertiaryBkg": "#dfe6e9"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    subgraph "📋 Demand Side (What)"
        PROJECT1("🎯 Project")
        STORY1("📖 Story 1")
        STORY2("📖 Story 2")
        STORY3("📖 Story 3")

        PROJECT1 --> STORY1
        PROJECT1 --> STORY2
        PROJECT1 --> STORY3
    end

    subgraph "⚙️ Supply Side (How)"
        PROJECT2("🎯 Project")
        WORKPLAN("📊 Workplan")
        MILESTONE1("🎯 Milestone 1")
        MILESTONE2("🎯 Milestone 2")

        PROJECT2 --> WORKPLAN
        WORKPLAN --> MILESTONE1
        WORKPLAN --> MILESTONE2
    end

    subgraph "🔗 Intersection"
        TASK1("✅ Task 1")
        TASK2("✅ Task 2")
        TASK3("✅ Task 3")
        TASK4("✅ Task 4")
        TASK5("✅ Task 5")
        TASK6("✅ Task 6")
    end

    %% Story to Task relationships
    STORY1 -.->|"story FK"| TASK1
    STORY1 -.->|"story FK"| TASK2
    STORY2 -.->|"story FK"| TASK3
    STORY2 -.->|"story FK"| TASK4
    STORY3 -.->|"story FK"| TASK5
    STORY3 -.->|"story FK"| TASK6

    %% Milestone to Task relationships
    MILESTONE1 --> TASK1
    MILESTONE1 --> TASK2
    MILESTONE1 --> TASK3
    MILESTONE2 --> TASK4
    MILESTONE2 --> TASK5
    MILESTONE2 --> TASK6

    %% Styling
    classDef demand fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef supply fill:#ff6b6b,stroke:#ff4757,stroke-width:3px,color:#000
    classDef task fill:#26de81,stroke:#20bf6b,stroke-width:2px,color:#000
    classDef intersection fill:#ffffff,stroke:#2f3542,stroke-width:2px,color:#000

    class STORY1,STORY2,STORY3 demand
    class WORKPLAN,MILESTONE1,MILESTONE2 supply
    class TASK1,TASK2,TASK3,TASK4,TASK5,TASK6 task
```

## Story State Machine

Stories flow through a defined lifecycle from idea to completion:

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3",
    "background": "#ffffff",
    "mainBkg": "#ffffff",
    "secondBkg": "#f1f2f6",
    "tertiaryBkg": "#dfe6e9"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart LR
    DRAFT("📝 draft")
    REFINEMENT("🔍 refinement")
    APPROVED("✅ approved")
    DONE("🎉 done")
    CANCELLED("❌ cancelled")

    DRAFT -->|"PO starts conversation"| REFINEMENT
    REFINEMENT -->|"PO accepts decomposition"| APPROVED
    REFINEMENT -->|"abandon idea"| CANCELLED
    APPROVED -->|"all tasks complete (auto)"| DONE
    APPROVED -->|"abandon work"| CANCELLED

    %% Styling
    classDef draft fill:#f1c40f,stroke:#f39c12,stroke-width:3px,color:#000
    classDef active fill:#3498db,stroke:#2980b9,stroke-width:3px,color:#000
    classDef approved fill:#2ecc71,stroke:#27ae60,stroke-width:3px,color:#000
    classDef terminal fill:#95a5a6,stroke:#7f8c8d,stroke-width:3px,color:#000
    classDef cancelled fill:#e74c3c,stroke:#c0392b,stroke-width:3px,color:#000

    class DRAFT draft
    class REFINEMENT active
    class APPROVED approved
    class DONE terminal
    class CANCELLED cancelled
```

**State Descriptions:**
- **draft**: Initial idea captured by PO
- **refinement**: PO and architect discussing scope and decomposition
- **approved**: PO accepted the task breakdown, work can begin
- **done**: All linked tasks completed (automatic transition)
- **cancelled**: Abandoned (cascades cancel to linked non-terminal tasks)

## Scenario 1: Tiny (1 Task, No Organization)

**Example**: "Fix typo in login error message"

Simple fixes that don't need organizational structure. The task floats independently.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3",
    "background": "#ffffff",
    "mainBkg": "#ffffff",
    "secondBkg": "#f1f2f6",
    "tertiaryBkg": "#dfe6e9"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    subgraph "🎯 Project: vtaskforge"
        STORY("📖 Fix login typo<br/>state: approved")
        TASK("✅ Update error message<br/>status: todo<br/>story: Fix login typo")

        STORY -.->|"story FK"| TASK
    end

    NOTE("💡 Task floats — no milestone or workplan needed<br/>Supervisor finds via 'vtf task list --status todo'")

    %% Styling
    classDef story fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef task fill:#26de81,stroke:#20bf6b,stroke-width:3px,color:#000
    classDef note fill:#f8f9fa,stroke:#495057,stroke-width:1px,color:#000

    class STORY story
    class TASK task
    class NOTE note
```

## Scenario 2: Small (Multiple Tasks, Existing Milestone)

**Example**: "Admin can force-transition tasks with audit trail"

Multiple related tasks that fit into existing organizational structure.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3",
    "background": "#ffffff",
    "mainBkg": "#ffffff",
    "secondBkg": "#f1f2f6",
    "tertiaryBkg": "#dfe6e9"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    subgraph "📊 Workplan: Core Features"
        subgraph "🎯 Milestone: Admin Tools"
            TASK1("✅ Backend endpoint<br/>PUT /tasks/:id/transition<br/>story: Force-transition")
            TASK2("✅ CLI command<br/>vtf task transition<br/>story: Force-transition")
            TASK3("✅ Web UI button<br/>Admin panel integration<br/>story: Force-transition")
            OTHERTASK("✅ Other admin task<br/>story: Different story")

            TASK1 --> TASK2
            TASK2 --> TASK3
        end
    end

    STORY("📖 Admin force-transition<br/>state: approved")

    %% Story links to its tasks
    STORY -.->|"story FK"| TASK1
    STORY -.->|"story FK"| TASK2
    STORY -.->|"story FK"| TASK3

    %% Styling
    classDef story fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef task fill:#26de81,stroke:#20bf6b,stroke-width:3px,color:#000
    classDef other fill:#95a5a6,stroke:#7f8c8d,stroke-width:2px,color:#000
    classDef milestone fill:#ff6b6b,stroke:#ff4757,stroke-width:2px,color:#000
    classDef workplan fill:#a55eea,stroke:#8e44ad,stroke-width:2px,color:#000

    class STORY story
    class TASK1,TASK2,TASK3 task
    class OTHERTASK other
```

**Key Point**: The story and milestone are parallel views. The story groups tasks by demand (what PO wants), while the milestone groups tasks by execution order.

## Scenario 3: Medium (Dedicated Milestone)

**Example**: "Add user story workflow to vtaskforge"

Complex features that need their own execution organization with dependencies.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3",
    "background": "#ffffff",
    "mainBkg": "#ffffff",
    "secondBkg": "#f1f2f6",
    "tertiaryBkg": "#dfe6e9"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    STORY("📖 Add user story workflow<br/>state: approved")

    subgraph "🎯 Milestone: Story Workflow (dedicated)"
        TASK1("✅ Database schema<br/>stories table")
        TASK2("✅ Story model<br/>SQLAlchemy class")
        TASK3("✅ API endpoints<br/>CRUD operations")
        TASK4("✅ CLI commands<br/>vtf story create/list")
        TASK5("✅ Web UI forms<br/>Story management")
        TASK6("✅ Story-task linking<br/>Foreign key support")
        TASK7("✅ State transitions<br/>draft→refinement→approved")
        TASK8("✅ Auto-completion<br/>done when tasks done")
        TASK9("✅ Integration tests<br/>E2E workflow")
        TASK10("✅ Documentation<br/>Usage guides")

        %% Dependencies
        TASK1 --> TASK2
        TASK2 --> TASK3
        TASK2 --> TASK6
        TASK3 --> TASK4
        TASK3 --> TASK5
        TASK6 --> TASK7
        TASK7 --> TASK8
        TASK4 --> TASK9
        TASK5 --> TASK9
        TASK8 --> TASK9
        TASK9 --> TASK10
    end

    %% All tasks belong to the story
    STORY -.->|"story FK"| TASK1
    STORY -.->|"story FK"| TASK2
    STORY -.->|"story FK"| TASK3
    STORY -.->|"story FK"| TASK4
    STORY -.->|"story FK"| TASK5
    STORY -.->|"story FK"| TASK6
    STORY -.->|"story FK"| TASK7
    STORY -.->|"story FK"| TASK8
    STORY -.->|"story FK"| TASK9
    STORY -.->|"story FK"| TASK10

    %% Styling
    classDef story fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef task fill:#26de81,stroke:#20bf6b,stroke-width:2px,color:#000
    classDef milestone fill:#ff6b6b,stroke:#ff4757,stroke-width:2px,color:#000

    class STORY story
    class TASK1,TASK2,TASK3,TASK4,TASK5,TASK6,TASK7,TASK8,TASK9,TASK10 task
```

**Characteristics**:
- Story ≈ one milestone's worth of work
- Complex DAG dependencies between tasks
- Dedicated milestone for execution ordering
- ~10-15 tasks typical for this scenario

## Scenario 4: Large (Multiple Stories, One Workplan)

**Example**: "Build vf-agents" → Architect splits into 4 focused stories

When the original request is too big, the architect breaks it into multiple stories during refinement.

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#ff6b6b",
    "primaryTextColor": "#000",
    "primaryBorderColor": "#ff4757",
    "lineColor": "#5f27cd",
    "secondaryColor": "#00d2d3",
    "tertiaryColor": "#ff9ff3",
    "background": "#ffffff",
    "mainBkg": "#ffffff",
    "secondBkg": "#f1f2f6",
    "tertiaryBkg": "#dfe6e9"
  },
  "flowchart": {
    "nodeSpacing": 50,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    subgraph "📊 Workplan: vf-agents (Epic-level)"
        subgraph "🎯 Milestone 1: Agent Registry"
            T1("✅ Agent model")
            T2("✅ Registration API")
            T3("✅ Agent discovery")
            T1 --> T2 --> T3
        end

        subgraph "🎯 Milestone 2: Task Matching"
            T4("✅ Capability matching")
            T5("✅ Load balancing")
            T6("✅ Assignment logic")
            T4 --> T5 --> T6
        end

        subgraph "🎯 Milestone 3: Execution"
            T7("✅ Task dispatch")
            T8("✅ Progress tracking")
            T9("✅ Result handling")
            T7 --> T8 --> T9
        end

        subgraph "🎯 Milestone 4: Monitoring"
            T10("✅ Health checks")
            T11("✅ Performance metrics")
            T12("✅ Alerting")
            T10 --> T11 --> T12
        end
    end

    %% Stories
    STORY1("📖 Agent Registration<br/>state: approved")
    STORY2("📖 Smart Task Assignment<br/>state: approved")
    STORY3("📖 Automated Execution<br/>state: approved")
    STORY4("📖 Agent Monitoring<br/>state: approved")

    %% Story to task relationships
    STORY1 -.->|"story FK"| T1
    STORY1 -.->|"story FK"| T2
    STORY1 -.->|"story FK"| T3

    STORY2 -.->|"story FK"| T4
    STORY2 -.->|"story FK"| T5
    STORY2 -.->|"story FK"| T6

    STORY3 -.->|"story FK"| T7
    STORY3 -.->|"story FK"| T8
    STORY3 -.->|"story FK"| T9

    STORY4 -.->|"story FK"| T10
    STORY4 -.->|"story FK"| T11
    STORY4 -.->|"story FK"| T12

    %% Styling
    classDef story fill:#00d2d3,stroke:#0097e6,stroke-width:3px,color:#000
    classDef task fill:#26de81,stroke:#20bf6b,stroke-width:2px,color:#000
    classDef milestone fill:#ff6b6b,stroke:#ff4757,stroke-width:2px,color:#000
    classDef workplan fill:#a55eea,stroke:#8e44ad,stroke-width:3px,color:#000

    class STORY1,STORY2,STORY3,STORY4 story
    class T1,T2,T3,T4,T5,T6,T7,T8,T9,T10,T11,T12 task
```

**Process**:
1. PO creates "Build vf-agents" story (draft)
2. During refinement, architect says "too big" and proposes 4 stories
3. Original story gets replaced by 4 focused stories
4. Each story ≈ one milestone of work
5. Workplan provides epic-level tracking
6. Each story completes independently when its tasks are done

## Scaling Decision Rules

The architect uses these rules during story refinement to determine appropriate scope:

| Story Size | Task Count | Organization | Decision Factors |
|------------|------------|-------------|------------------|
| **Tiny** | 1 task | No milestone/workplan | Simple fix, single file change, < 1 hour |
| **Small** | 2-5 tasks | Existing milestone | Related changes, can fit in current sprint |
| **Medium** | 5-15 tasks | Dedicated milestone | Complex feature, needs DAG dependencies |
| **Large** | 15+ tasks | Split into multiple stories | Too big for one story, architect breaks down |

## Story Completion Logic

Stories automatically transition to `done` when all linked tasks reach `done` status:

```sql
-- Auto-transition logic
UPDATE stories
SET state = 'done', completed_at = NOW()
WHERE state = 'approved'
  AND NOT EXISTS (
    SELECT 1 FROM tasks
    WHERE tasks.story = stories.id
      AND tasks.status != 'done'
  );
```

## Key Design Principles

1. **Orthogonal Views**: Stories (demand) and milestones (supply) are independent organizational views
2. **Flexible Linking**: Tasks can exist without stories, stories without milestones
3. **Automatic Completion**: Story state updates automatically based on task completion
4. **Scaling Boundaries**: Clear rules for when to split stories vs. create milestones
5. **Epic-Level Tracking**: Workplans provide portfolio-level visibility for large initiatives

## Implementation Notes

- `task.story` is a nullable foreign key to `stories.id`
- Story state machine enforces proper workflow
- Cancelled stories cascade cancel to linked non-terminal tasks
- Story completion is computed, not manually set
- PO owns stories, architect owns task decomposition and organization