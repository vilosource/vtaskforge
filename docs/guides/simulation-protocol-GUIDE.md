# Simulation Protocol Guide

Manual supervisor workflow for executing vtf tasks using Claude Code subagents as executor and judge, without the vafi controller infrastructure.

## Overview

The simulation replaces the automated vafi controller loop with a human supervisor (you) orchestrating Claude Code subagents. The executor and judge agents do real work — the simulation is only in how they're dispatched.

```
You (Supervisor)
  ├── vtf board: pick task, manage lifecycle
  ├── git: create branches, merge on accept
  ├── dispatch: spawn executor agent with spec
  ├── dispatch: spawn judge agent with diff
  └── decide: accept/reject based on judge verdict
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
- [ ] Docker dev stack is running: `cd ~/GitHub/vtaskforge && docker compose ps`
- [ ] Git is on develop, clean: `git status` shows no uncommitted changes
- [ ] vafi executor is scaled to 0: `KUBECONFIG=~/.kube/vafi-dev.yaml kubectl get pods -n vafi-agents` shows no pods
- [ ] Tasks are in `todo` on the board: `vtf task list --workplan <id>`

## Supervisor Workflow

### 1. Pick a Task

```bash
vtf task list --status todo --workplan <workplan-id>
```

Choose the next task respecting dependencies. Tasks with unresolved dependencies can't be started.

### 2. Claim the Task

```bash
vtf task claim <task-id> --agent supervisor --tags supervisor
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

## Task Spec
<paste spec YAML here>

## Branch
Check out branch: task/<task-id>

Implement the task following your methodology. Commit when done.
---
```

Model: `sonnet` (or as specified in spec's `agent_model` field)

### 6. Review the Executor Output

The executor returns a completion report. Read it. Note:
- Were all acceptance criteria claimed as MET?
- Any spec deviations?
- Any blast radius discoveries?

### 7. Run Test Gate (Supervisor Responsibility)

The executor should have run tests, but verify independently:

```bash
cd ~/GitHub/vtaskforge
git checkout task/<task-id>
docker compose exec api pytest --tb=short
```

If tests fail, skip the judge and send back to executor for fixes.

### 8. Dispatch the Judge

Use the Agent tool with `subagent_type: vtf-judge`:

```
Prompt template:
---
Review the implementation for a vtf task. Work in /home/jasonvi/GitHub/vtaskforge/.

## Task Spec
<paste spec YAML here>

## Branch to Review
Review branch: task/<task-id>
Base branch: develop

Diff command: git diff develop...task/<task-id>

## Executor Completion Report
<paste executor's report here>

Produce your verdict.
---
```

Model: `opus` (judge needs deeper reasoning)

### 9. Decision

Based on the judge verdict:

#### PASS → Accept and Merge

```bash
cd ~/GitHub/vtaskforge
git checkout develop
git merge task/<task-id>
git branch -d task/<task-id>
vtf task complete <task-id>
```

#### FAIL → Rework

```bash
vtf task block <task-id>   # or keep in doing
```

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

Then re-run the judge (include previous verdict for rework awareness).

### 10. Update the Board

After merge:
```bash
vtf task complete <task-id>
```

After max rework attempts (3) with no resolution:
```bash
vtf task fail <task-id>
```

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
Attempt 1: Executor implements → Judge reviews → FAIL
Attempt 2: New executor (spec + judge feedback) on same branch → Judge reviews → FAIL
Attempt 3: New executor (spec + latest judge feedback) on same branch → Judge reviews → FAIL
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
