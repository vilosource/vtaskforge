# Simulation Protocol Guide

Manual supervisor workflow for executing vtf tasks using Claude Code subagents as executor and judge, without the vafi controller infrastructure.

## Prerequisites

This protocol assumes tasks are already in `todo` status with detailed specs. If tasks are in `draft`, run the [Workplan Review Protocol](../workplan-review-PROTOCOL.md) first to verify assumptions, author specs, and move tasks to `todo`.

The full pipeline is: **Observation → Backlog → Workplan → Review → Execution (this protocol) → Verification**. See the review protocol for details on the upstream stages.

## Overview

The simulation replaces the automated vafi controller loop with a human supervisor (you) orchestrating Claude Code subagents. The executor and judge agents do real work — the simulation is only in how they're dispatched.

### Roles

| Role | Responsibility | Does NOT |
|------|---------------|----------|
| **Supervisor** (you) | Orchestrates: picks tasks, dispatches agents, creates branches, merges on accept, decides accept/reject | Run tests, write code, review code |
| **Executor** (subagent) | Implements: reads spec, writes code, runs tests during TDD (self-check), commits | Make design decisions, push, run final verification |
| **Judge** (subagent) | Verifies: runs tests against baseline (verification gate), reviews code, checks blast radius, produces verdict | Modify code, implement fixes, make design decisions |

The supervisor orchestrates. The executor implements. The judge verifies. No role does another role's work.

```
Supervisor                    Executor              Judge
  │                              │                    │
  ├── claim task                 │                    │
  ├── create branch              │                    │
  ├── dispatch executor ────────►│                    │
  │                              ├── orient           │
  │                              ├── implement (TDD)  │
  │                              ├── commit           │
  │◄── completion report ────────┤                    │
  │                                                   │
  ├── dispatch judge ────────────────────────────────►│
  │                                                   ├── run tests (vs baseline)
  │                                                   ├── review code
  │                                                   ├── check blast radius
  │◄── verdict ──────────────────────────────────────┤
  │
  ├── PASS → merge, complete
  └── FAIL → dispatch executor rework
```

## Three-Layer Context Model

Each agent receives context from three sources:

| Layer | Source | Contains |
|-------|--------|----------|
| Repo CLAUDE.md | Auto-discovered by agent (Step 0) | Stack, test commands, project structure, conventions |
| Agent definition | `~/.claude/agents/vtf-executor.md` or `vtf-judge.md` | Role-specific methodology, report format, scope rules |
| Task spec | Pasted into prompt by supervisor | What to build, files, approach, constraints, acceptance criteria |

## Pre-Flight Checklist

Before starting a simulation session:

- [ ] vtf CLI points at prod: `vtf config show` → `https://vtf.viloforge.com`
- [ ] vtf token is valid: `vtf health` returns healthy
- [ ] Docker dev stack is running: `cd ~/GitHub/vtaskforge && docker compose up -d && docker compose ps`
- [ ] Git is on develop, clean: `git status` shows no uncommitted changes
- [ ] vafi executor is scaled to 0: `KUBECONFIG=~/.kube/vafi-dev.yaml kubectl get pods -n vafi-agents` shows no pods
- [ ] Tasks are in `todo` on the board: `vtf task list --workplan <id>`
- [ ] **Baseline test count known**: the previous milestone's quality gate recorded the count. If this is the first milestone, run E0 to establish it.

**The baseline is verified by the quality gate task (G<N>) at the end of each milestone, not per task.** The quality gate is the only task that runs the full test suite.

## Supervisor Workflow

### 1. Pick a Task

```bash
vtf task list --status todo --workplan <workplan-id>
```

Choose the next task respecting dependencies. Tasks with unresolved dependencies can't be started.

### 2. Claim the Task

```bash
vtf task claim <task-id> --agent <agent-id> --tags supervisor
```

### 3. Fetch the Spec

```bash
vtf task show <task-id> --json
```

Copy the `.spec` field content — this is what the executor receives.

### 4. Create a Branch

```bash
cd ~/GitHub/vtaskforge
git checkout develop
git pull
git checkout -b task/<task-id>
```

### 5. Dispatch the Executor

Use the Agent tool with `subagent_type: vtf-executor`:

```
Prompt template:
---
You are implementing a vtf task. Work in /home/jasonvi/GitHub/vtaskforge/ on branch task/<task-id>.

## Task ID
<task-id>

## Task Spec
<paste spec YAML here>

## Branch
Check out branch: task/<task-id>

Implement the task following your methodology. Commit when done.
After committing, call vtf_submit_work(task_id="<task-id>", agent_id="executor-<task-id>") to submit your work.
---
```

Model: `sonnet` (or as specified in spec's `agent_model` field)

**Important:** The executor calls `vtf_submit_work` directly — the supervisor does NOT relay this call. This establishes the executor's identity in vtf for the reviewer != claimer enforcement.

### 6. Review the Executor Output

The executor returns a completion report. Read it. Note:
- Were all acceptance criteria claimed as MET?
- Any spec deviations?
- Any blast radius discoveries?
- Did the executor successfully call `vtf_submit_work`? If not, the supervisor calls it with `agent_id="executor-<task-id>"` (not the supervisor's own ID).

Do NOT verify the executor's claims yourself — that's the judge's job. You just read the report to understand what was done.

Do NOT call `vtf_review_task` yourself — that's the judge's job. vtf enforces this: the reviewer cannot be the same agent that claimed the task.

### 7. Dispatch the Judge

Use the Agent tool with `subagent_type: vtf-judge`:

```
Prompt template:
---
Verify the implementation for a vtf task. Work in /home/jasonvi/GitHub/vtaskforge/.

## Task ID
<task-id>

## Task Spec
<paste spec YAML here>

## Branch to Review
Review branch: task/<task-id>
Base branch: develop

## Executor Completion Report
<paste executor's report here>

Run the task-specific tests (test_command.unit from the spec), review the code, and produce your verdict.
After producing your verdict, call vtf_review_task(task_id="<task-id>", decision="approved" or "changes_requested", reviewer_id="judge-<task-id>", reason="<summary>").
---
```

Model: `opus` (judge needs deeper reasoning)

The judge will:
1. Run the task-specific tests
2. If tests fail → automatic FAIL, skip code review
3. If tests pass → full code review, blast radius check, pattern compliance
4. Produce a structured verdict
5. Call `vtf_review_task` directly with the verdict

**Important:** The judge calls `vtf_review_task` directly — the supervisor does NOT relay this call. vtf enforces that the reviewer is a different agent than the claimer.

### 8. Decision

Based on the judge verdict (check vtf task status — if the judge approved, it's already `done`):

#### PASS → Merge

```bash
cd ~/GitHub/vtaskforge
git checkout develop
git merge task/<task-id>
git branch -d task/<task-id>
# Task is already done — judge approved it via vtf_review_task
```

#### FAIL → Rework

Dispatch a new executor with the original spec + judge feedback:

```
Prompt template:
---
You are reworking a vtf task after judge rejection. Work in /home/jasonvi/GitHub/vtaskforge/ on branch task/<task-id>.

## Task Spec
<paste spec YAML here>

## Branch
Check out branch: task/<task-id> (has previous attempt's commits)

## Judge Feedback
<paste judge verdict here>

Fix the BLOCKING issues. Do not reimplement from scratch — build on existing work.
---
```

Then re-dispatch the judge (include previous verdict for rework awareness).

### 9. Update the Board

After merge:
```bash
vtf task complete <task-id>
```

After max rework attempts (3) with no resolution:
```bash
vtf task fail <task-id>
```

## Quality Gates as Tasks

Every milestone must end with a quality gate task. Quality gates are regular tasks on the board — they go through the same executor→judge loop as implementation tasks.

**What a quality gate task does:**
- Runs the full test suite (backend + CLI + frontend) — the complete regression check
- Verifies the milestone's checklist (from the implementation plan)
- Reports the updated baseline test count

**Why it's a task, not a manual step:**
- The supervisor doesn't do work — quality verification is work
- It's tracked on the board like everything else
- It goes through the judge for independent confirmation
- In vafi, the controller dispatches it like any other task

**Naming convention:** `G<N>` — e.g., `G0` (after Phase 0), `G1` (after Phase 1)

**Dependency:** The quality gate depends on ALL tasks in its milestone.

**Example spec structure:**
```yaml
id: "G1"
name: "Quality Gate: Phase 1 complete"
depends_on: [P1.1, P1.2, P1.3]
judge: true

acceptance_criteria:
  - "Full backend test suite passes with 0 failures"
  - "CLI test suite passes with 0 failures"
  - "MCP server starts via python -m mcp_server.server"
  - "vtf_board_overview tool returns correct data"
  - "Response format matches SPECIFICATION.md"
```

**Test execution model:**
- Per task: executor and judge run `test_command.unit` only (lean context, fast)
- Quality gate task: executor runs `test_command.full` + CLI tests (complete regression)
- This is the ONLY time the full suite runs during a milestone

## Branch Naming Convention

```
task/<task-id>          # e.g., task/JsfatyOL79NvvmUPoVwfR
```

Use the vtf task ID, not the spec ID (P0.1). The vtf ID is globally unique.

## Parallel Execution

When tasks have no dependency conflicts:

1. Create separate branches for each task
2. Dispatch multiple executors simultaneously (each on its own branch)
3. Judge each independently
4. Merge to develop in dependency order

Check for file conflicts before merging the second branch:
```bash
git checkout develop
git merge task/<first-id>
git merge task/<second-id>   # if conflict, resolve manually
```

## Rework Flow Detail

```
Attempt 1: Executor implements → Judge verifies → FAIL
Attempt 2: New executor (spec + judge feedback) on same branch → Judge verifies → FAIL
Attempt 3: New executor (spec + latest judge feedback) on same branch → Judge verifies → FAIL
Attempt 4: DO NOT RETRY. vtf task fail <id>. Escalate to human.
```

Max 3 rework attempts. After that, the task needs human intervention.

## Known Limitations vs vafi

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| No agent continuity | Each executor is a fresh session, no memory of previous work | Rework executor gets spec + judge feedback in prompt |
| No session resumption | Can't `claude --resume` between attempts | New agent checks out existing branch, reads existing code |
| No heartbeats | vtf doesn't know if executor is alive | Supervisor monitors agent manually |
| No automatic claim expiry recovery | If supervisor session dies mid-task, task stays in `doing` | Manually unblock/reset via vtf CLI |
| Single machine | All agents share one filesystem | Use branches for isolation, not worktrees (worktrees don't work with subagents) |

## Lessons Learned

### Baseline before everything
The executor reported "27 pre-existing test failures" during the first attempted run. Without a baseline, the supervisor couldn't verify this claim. Always establish the baseline before dispatching any executor.

### The supervisor doesn't do work
The supervisor orchestrates — it does not run tests, write code, or review code. If something needs to be verified, dispatch the right agent. If you find yourself doing work as the supervisor, stop and ask: which agent should be doing this?

### Tests before code review
If the judge finds test regressions, it should FAIL immediately and skip the code review. Reviewing broken code wastes tokens and time. Tests are cheap verification; code review is expensive verification. Cheap first, expensive second.

### Verify branch before dispatching executor
The executor committed to develop instead of its task branch during the Breadcrumbs milestone. The supervisor should verify `git branch --show-current` matches the expected branch before dispatching. In vafi, the controller handles branch checkout — executors should never touch branching.

### Claim just-in-time, not in batches
Claiming all tasks up front wastes the 30-minute claim window on tasks that won't execute for a while. Claim one task (or one parallel batch) at a time, right before dispatching the executor.

### Use test deltas, not absolute counts
Branches forked from develop have different test counts because each adds its own tests. Executor and judge should report "added N tests, baseline was M at fork point" — not just the total. The quality gate is the only place the integrated count matters.

### Review protocol is the highest-leverage investment
The Breadcrumbs milestone had zero rework cycles. This is because the review protocol (draft → ready) caught false assumptions and enriched specs before execution. A well-specified task is hard for an executor to get wrong. For vafi, invest more in the review agent than the executor agent.

## Quick Reference: Task IDs (MCP Server Phase 0)

| Spec ID | vtf ID | Task |
|---------|--------|------|
| P0.1 | JsfatyOL79NvvmUPoVwfR | EventService extraction |
| P0.2 | 4ZA_IGK22MjMXp0N1qyaN | Dependency resolution |
| P0.3 | ALtsF2jg6XMeI2BOlqhB8 | Claim logic |
| P0.4 | sI7EKT6QYytjKYRdpdnWi | Find claimable |
| P0.5 | JRmVbvMBwFZ9MggAyzzI8 | ReviewService |
| P0.6 | fzw-czSWG6yVGmElCZR8I | Celery fix |
| P0.7 | JOsGidfy9grKhr-B9_R1p | Enrichment helpers |

Workplan: `DcKhKOd37IHFdHNmgUefm` (MCP Server)
Milestone: `n7Oq32glw4-3dJInVC3SL` (mcp-phase0)
Project: `vT2Z1IyVylzdcV44gZ1-O` (VTaskForge)
