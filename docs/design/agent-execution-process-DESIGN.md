# Agent Execution Process Design

## Status: Living document (updated 2026-03-21)
## Date: 2026-03-21

## Context

This document defines how tasks flow through vtaskforge with three actor types:
Supervisor, Executor, and Judge. The process was discovered through dogfooding —
executing Phase 8 (rename) with real agents and learning from what went wrong.

**Current state:** We simulate the process manually. Claude Code subagents play
executors, the vtf-judge agent definition exists, and the human+AI session acts
as supervisor. There is no vf-agents system yet.

**Future state:** vf-agents will encode this process in code — the supervisor's
control loop, the executor's boundaries, the judge's verification, and the
reject/rework cycle will all be automated.

## Three Actors, Three Responsibilities

| Actor | Role | Board Operations | Analogy |
|-------|------|-----------------|---------|
| **Supervisor** | Orchestrate work, manage milestones, handle escalations | Submit (draft→todo), cancel, defer, unblock | Engineering Manager |
| **Executor** | Write code, implement specs | Claim (todo→doing), complete (doing→pending_completion_review) | Developer |
| **Judge** | Verify quality, enforce standards | Submit review (approved→done or changes_requested) | Code Reviewer |

Each actor owns only their natural transitions. No actor does another's job.

## Diagram 1: Task Lifecycle — Who Owns Each Transition

```mermaid
%%{init: {
  "theme": "neutral",
  "themeVariables": {
    "primaryColor": "#4285f4",
    "primaryTextColor": "#000",
    "lineColor": "#333",
    "background": "#ffffff"
  },
  "flowchart": {
    "nodeSpacing": 40,
    "rankSpacing": 50,
    "curve": "basis"
  }
}}%%

flowchart TB
    DRAFT("📝 draft")
    TODO("📋 todo")
    DOING("⚙️ doing")
    PENDING("🔍 pending_completion_review")
    DONE("✅ done")
    CHANGES("🔄 changes_requested")
    BLOCKED("🚫 blocked")
    ATTENTION("⚠️ needs_attention")
    CANCELLED("❌ cancelled")
    DEFERRED("⏸️ deferred")

    %% Supervisor transitions (blue)
    DRAFT -->|"👑 SUPERVISOR submits"| TODO
    TODO -->|"👑 SUPERVISOR cancels"| CANCELLED
    DOING -->|"👑 SUPERVISOR cancels"| CANCELLED
    TODO -->|"👑 SUPERVISOR defers"| DEFERRED
    DOING -->|"👑 SUPERVISOR defers"| DEFERRED
    ATTENTION -->|"👑 SUPERVISOR resets"| TODO

    %% Executor transitions (green)
    TODO -->|"🔧 EXECUTOR claims"| DOING
    DOING -->|"🔧 EXECUTOR submits for review"| PENDING
    CHANGES -->|"🔧 EXECUTOR resubmits"| PENDING
    DOING -->|"🔧 EXECUTOR gives up"| ATTENTION
    TODO -->|"🔧 EXECUTOR blocked"| BLOCKED
    DOING -->|"🔧 EXECUTOR blocked"| BLOCKED

    %% Judge transitions (orange)
    PENDING -->|"⚖️ JUDGE approves"| DONE
    PENDING -->|"⚖️ JUDGE rejects"| CHANGES

    %% Styling
    classDef draft fill:#f3f4f6,stroke:#9ca3af,stroke-width:2px,color:#000
    classDef active fill:#dbeafe,stroke:#3b82f6,stroke-width:2px,color:#000
    classDef review fill:#fef3c7,stroke:#f59e0b,stroke-width:2px,color:#000
    classDef terminal fill:#d1fae5,stroke:#10b981,stroke-width:2px,color:#000
    classDef problem fill:#fee2e2,stroke:#ef4444,stroke-width:2px,color:#000
    classDef paused fill:#e5e7eb,stroke:#6b7280,stroke-width:2px,color:#000

    class DRAFT draft
    class TODO,DOING active
    class PENDING,CHANGES review
    class DONE terminal
    class CANCELLED,DEFERRED paused
    class BLOCKED,ATTENTION problem
```

## Diagram 2: Happy Path — Task Succeeds First Try

```mermaid
sequenceDiagram
    participant S as 👑 Supervisor
    participant B as 📋 Board
    participant E as 🔧 Executor
    participant J as ⚖️ Judge

    Note over S: Milestone activated, task specs ready

    S->>B: Submit task (draft → todo)
    S->>E: Dispatch executor
    E->>B: Claim task (todo → doing)
    E->>E: Read spec, work in worktree
    E->>E: Write code, run local checks
    E->>E: Commit changes
    E->>B: Submit for review (doing → pending_completion_review)
    E->>S: Report: "work finished"

    S->>J: Dispatch judge for task
    J->>J: Run test_command from spec
    J->>J: Review code against acceptance_criteria
    J->>B: Submit review: approved
    Note over B: Task → done
    J->>S: Report: "approved"

    S->>S: Check DAG — submit next tasks whose deps are met

    Note over B: If all milestone tasks done → auto-complete milestone
```

## Diagram 3: Reject/Rework Loop — Task Needs Fixes

```mermaid
sequenceDiagram
    participant S as 👑 Supervisor
    participant B as 📋 Board
    participant E as 🔧 Executor
    participant J as ⚖️ Judge

    E->>B: Submit for review (doing → pending_completion_review)
    E->>S: Report: "work finished"

    S->>J: Dispatch judge for task
    J->>J: Run test_command
    Note over J: ❌ 262 test failures

    J->>B: Submit review: changes_requested
    Note over B: Comment: "262 failures,<br/>fixture 'phase' not found in 16 files"
    Note over B: Task → changes_requested
    J->>S: Report: "rejected — see review comment"

    S->>S: Attempt 1 of 3 failed
    S->>E: Dispatch executor for rework
    Note over S: "Task rejected. Read review<br/>comments and fix the issues."

    E->>E: Read review comments from API
    E->>E: Fix issues, commit
    E->>B: Resubmit (changes_requested → pending_completion_review)
    E->>S: Report: "rework finished"

    S->>J: Dispatch judge again
    J->>J: Run test_command
    Note over J: ✅ All tests pass
    J->>J: Review code against spec
    Note over J: ✅ Acceptance criteria met
    J->>B: Submit review: approved
    Note over B: Task → done
    J->>S: Report: "approved"

    Note over S: If 3 attempts all fail:<br/>escalate to human
```

## Diagram 4: Supervisor Orchestration — Full Milestone Execution

```mermaid
sequenceDiagram
    participant H as 👤 Human
    participant S as 👑 Supervisor
    participant B as 📋 Board
    participant E1 as 🔧 Executor 1
    participant E2 as 🔧 Executor 2
    participant J as ⚖️ Judge

    H->>S: "Execute milestone X"
    S->>B: Activate milestone
    S->>B: Submit tasks with no deps (draft → todo)

    par Supervisor dispatches executors in parallel
        S->>E1: Dispatch for task A
        E1->>B: Claim task A
        E1->>E1: Work on task A
        E1->>B: Submit for review
        E1->>S: Report: "finished"
    and
        S->>E2: Dispatch for task B
        E2->>B: Claim task B
        E2->>E2: Work on task B
        E2->>B: Submit for review
        E2->>S: Report: "finished"
    end

    S->>J: Dispatch judge for task A
    J->>B: Review task A → approved ✅
    J->>S: "Task A approved"

    S->>J: Dispatch judge for task B
    J->>B: Review task B → changes_requested ❌
    J->>S: "Task B rejected"

    S->>E2: Dispatch for rework on task B
    E2->>B: Resubmit rework
    E2->>S: "Rework finished"

    S->>J: Dispatch judge for task B (attempt 2)
    J->>B: Review task B → approved ✅
    J->>S: "Task B approved"

    Note over S: Tasks A, B done → check DAG → deps met for task C
    S->>B: Submit task C (draft → todo)

    S->>E1: Dispatch for task C
    E1->>B: Claim task C
    E1->>E1: Work on task C
    E1->>B: Submit for review
    E1->>S: "Finished"

    S->>J: Dispatch judge for task C
    J->>B: Review task C → approved ✅

    Note over B: All tasks done → milestone auto-completes

    S->>H: "Milestone X complete"
```

## Quality Gates

Every task passes through up to three gates before reaching `done`:

| Gate | Who | What | When |
|------|-----|------|------|
| **test_command** | Judge | Run the automated test suite from the task spec | Always |
| **Spec review** | Judge | Compare implementation against acceptance_criteria | Always |
| **Human review** | Human | Visual verification, UX judgment, architectural decisions | Verification gates only (e.g., task 8.7) |

The judge combines gates 1 and 2. Gate 3 only applies to special verification
tasks at the end of a milestone.

## Escalation Paths

| Situation | Who detects | Action |
|-----------|-------------|--------|
| Executor can't complete task | Executor | Transition to `needs_attention`, supervisor reassigns |
| Task blocked by dependency | Executor | Transition to `blocked`, supervisor resolves |
| Judge rejects 3 times | Judge/Supervisor | Supervisor escalates to human |
| Executor claim expires | Supervisor (via Celery) | Auto-unclaim, task returns to `todo` |
| All tasks done in milestone | System (auto-completion) | Milestone → `completed` |

## How We Simulate This Today

Since vf-agents doesn't exist yet, we simulate the process manually:

| vf-agents role | Current simulation |
|----------------|-------------------|
| Supervisor agent | Human + Claude Code session (me) |
| Executor agent | Claude Code subagent (Agent tool with worktree isolation) |
| Judge agent | Claude Code vtf-judge agent (or manual verification) |
| Board | vtaskforge dogfood instance at localhost:8001 |
| Task specs | YAML files in phases/ directory, imported via vtf CLI |

### What the executor subagent receives

```
Prompt: "Execute vtf task <ID>"
- Claim the task (todo → doing)
- Read the spec (vtf task show <ID> --json)
- Do the work in the worktree
- Commit changes
- Transition to pending_completion_review
- Report back what was done
```

### What the supervisor (me) does

```
1. Activate milestone, submit tasks respecting DAG deps
2. Dispatch executor subagents for todo tasks
3. When executor reports "finished" → dispatch judge subagent
4. Judge runs test_command + reviews against spec
5. Judge submits formal review via API (approved or changes_requested with comment)
6. If rejected → dispatch executor again with "read the review comments"
7. If approved → check DAG, submit next tasks whose deps are met
8. Track retry count — escalate to human after 3 failures
9. When all tasks done → verify milestone auto-completed
```

The supervisor NEVER runs tests or reviews code directly. It dispatches
and monitors. The judge does all verification.

## Lessons from Phase 8 (2026-03-21)

These findings directly inform the vf-agents architecture:

1. **Agents cannot self-report completion.** Task 8.2 declared success with 262
   test failures. The judge gate is mandatory, not optional.

2. **Board operations must match actor roles.** Executor claims and submits for
   review. Judge approves or rejects. Supervisor orchestrates. When we mixed
   these up (executor completing, supervisor fixing code), the process broke.

3. **Reject with feedback, never fix directly.** The supervisor fixed broken
   agent work instead of rejecting it back. This doesn't scale and leaves no
   audit trail.

4. **Atomic operations need atomic execution.** Splitting a rename across 4
   parallel agents created merge conflicts. One agent per atomic change.

5. **Task boundaries should minimize file overlap.** Split by module (workplans
   app, tasks app) not by layer (backend, tests, CLI) when files are shared.

6. **Numerical verification over visual.** Use getBoundingClientRect(), test
   counts, grep counts — never eyeball screenshots.

## What vf-agents Must Encode

When we build the agent pool manager, it must implement:

1. **Supervisor control loop** — activate milestones, submit tasks respecting
   DAG deps, monitor progress, handle escalations
2. **Executor boundaries** — can claim and submit for review, cannot mark done
3. **Judge automation** — watches pending_completion_review queue, runs
   test_command, reviews against spec, submits formal review
4. **Reject/rework cycle** — changes_requested with actionable feedback,
   executor picks up rework, max 3 retries before escalation
5. **Deploy agent** — Docker builds, migrations, dogfood restarts (currently
   manual)
6. **Smoke-test agent** — Playwright verification with numerical checks
   (currently manual)
7. **Spec writer agent** — reads design docs, produces YAML task specs
   (currently human+AI collaborative)
