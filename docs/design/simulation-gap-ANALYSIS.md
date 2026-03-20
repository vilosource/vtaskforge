# Simulation Gap Analysis

Status: Active (2026-03-20)

## Problem Statement

Phases 0-2 of vtaskforge were executed through a **manual simulation** that diverged significantly from the documented process. The supervisor role was performed by a human-in-the-loop Opus agent that hand-crafted executor prompts, made ad-hoc gating decisions, and applied contextual knowledge that won't be available when the standardized agent pipeline runs autonomously.

The process guide (phase-process-GUIDE.md) describes a systematic flow — supervisor reads board, dispatches standardized executor, runs gates, dispatches judge — but this flow was never tested as an integrated system. Each component was validated in isolation (task specs work, tests pass, judge produces verdicts) but the **orchestration** was always manual.

This means our retrospective findings are based on a process that doesn't exist yet. The "process improvements" we documented (contracts, affected_files, pattern templates, tiered judge policy) optimize a manual workflow that will be replaced by an automated one. They may or may not transfer.

## What Was Actually Tested

| Component | Tested? | How |
|---|---|---|
| Task spec format (YAML) | Yes | Sonnet agents executed from specs successfully |
| Behavioral specs | Partially | Judge verified 2 of 12 tasks in Phase 1, 0 in Phase 2 |
| Gate 1 (mechanical tests) | Yes | pytest run after every task |
| Gate 2 (judge code review) | Partially | Ad-hoc prompts, inconsistent scope |
| Black-box testing | Yes | 4 scenarios verified end-to-end |
| Executor agent (standardized) | No | Hand-crafted prompts each time |
| Judge agent (standardized) | No | Ad-hoc prompts each time |
| Supervisor agent (orchestration) | No | Manual orchestration by Opus |
| vtf CLI for task tracking | No | Tracked via markdown, not vtf |
| Parallel agent coordination | Partially | 2 parallel rounds worked, but coordinated manually |

## The Gap

### 1. Executor Prompt Quality

During Phases 1-2, the supervisor (Opus) added contextual glue to each executor dispatch:
- Task-specific "important" notes ("Note inherits NanoIDMixin only, NOT TimestampMixin")
- Reminders about which files to read first
- Warnings about tricky parts ("you're REPLACING the existing claim action")
- Docker commands customized to the task

The standardized executor agent receives:
- Its system prompt (generic process rules)
- The task spec YAML (the implementation details)

**Question:** Is the YAML spec alone sufficient, or did the hand-crafted glue carry essential context? If Sonnet fails tasks that it previously passed, the gap is in the spec or the agent prompt.

### 2. Supervisor Decision Making

The manual supervisor made judgment calls that aren't codified:
- "This task is simple CRUD, skip the judge" (tiered judge policy was informal)
- "The test suite time jumped from 4s to 47s — worth noting but not blocking"
- "The agent committed already, let me just stage the execution log"
- "These three tasks can run in parallel" (manual file overlap analysis)

The supervisor agent needs to make these decisions from rules, not intuition.

### 3. Judge Consistency

The judge was invoked twice in Phase 1 with different prompts:
- Task 1.1: curl-based behavior verification (duplicated tests)
- Task 1.5: structural code review against design doc (genuinely valuable)

We then redefined the judge as "code reviewer, not behavior tester" in the process guide, but this redefined role was never tested.

### 4. Error Recovery

No task failed during Phases 1-2, so the failure handling path is completely untested:
- Executor retry on Gate 1 failure
- Judge feedback loop
- `vtf task fail` and triage
- Escalation from Sonnet to Opus

## What Phase 3 Validates

Phase 3 is the first end-to-end test of the integrated agent pipeline:

| Component | Phase 3 validation |
|---|---|
| vtf-supervisor agent | Drives the entire phase — reads board, dispatches, gates, updates |
| vtf-executor agent | Receives standardized prompt + YAML spec, no hand-crafted glue |
| vtf-judge agent | Follows consistent code review format when judge: true |
| vtf CLI tracking | All task state managed through vtf, not markdown |
| Parallel coordination | Supervisor decides and coordinates parallel dispatch |
| Error recovery | If a task fails, we see how the supervisor handles it |

## Expected Outcomes

### Optimistic case
The YAML specs are detailed enough that the standardized executor handles everything. The supervisor correctly orchestrates the flow. Phase 3 completes like Phases 1-2 but with less manual intervention.

### Likely case
Some tasks fail on first attempt because the executor misses context that was previously hand-crafted. The supervisor's retry/escalation path gets exercised. We learn which specs need more detail and which executor prompt elements are essential.

### Pessimistic case
The standardized executor consistently fails, requiring manual intervention to add context. This would mean our spec format needs a fundamental rethink — perhaps adding a "context" or "gotchas" section that captures what the manual supervisor was adding.

## Metrics to Track

For each Phase 3 task, compare against Phase 1-2 baselines:
- **First-attempt success rate**: Phase 1-2 was 100%. Will it hold with standardized prompts?
- **Retries needed**: Phase 1-2 was 0. How many retries does the automated pipeline need?
- **Escalations**: How many tasks need Opus instead of Sonnet?
- **Supervisor interventions**: How many times does the human need to step in?
- **Spec amendments**: How many specs need updating after the executor fails?
- **Time per task**: Is automated orchestration faster or slower than manual?

## Recommendations

1. **Treat Phase 3 as a pipeline validation**, not just a feature delivery. The feature work (fixes, pagination, SSE) is secondary to validating the agent orchestration.

2. **Start with simple tasks** (3.1, 3.2, 3.3 — small fixes) to calibrate the pipeline before the complex ones (3.4, 3.5 — pagination, SSE).

3. **Be ready to iterate on agents** after the first few tasks. If the executor fails, update its system prompt. If the supervisor makes bad decisions, update its rules. This is the learning loop.

4. **Document every intervention** — every time a human steps in to fix something the supervisor couldn't handle, that's a process gap to codify.

5. **Don't optimize prematurely** — if the manual process worked and the automated one doesn't, understand why before adding complexity. The answer might be "add one sentence to the executor prompt," not "redesign the spec format."
