# Execution Pipeline Architecture

## Overview

Work flows through a pipeline of stages from user observation to verified code. Each stage has a distinct role, input, output, and level of spec detail. No role does another role's work.

```
Observation ──► Backlog ──► Workplan ──► Review ──► Execution ──► Verification
  (human)      (planner)   (planner)   (reviewer)  (executor)     (judge)
```

## Stages

### 1. Observation
**Role**: Human
**Input**: User experience, pain points, ideas
**Output**: Short description captured as draft task or backlog item
**Spec detail**: None — intent only ("breadcrumbs are inconsistent")

Observations are quick, unstructured, at varying granularity. Some are bugs, some are features, some are polish. They accumulate over days. No technical analysis required.

### 2. Backlog
**Role**: Human + Planner
**Input**: Observations, priorities, product context
**Output**: Scoped work items with goal, context, and rough acceptance criteria
**Spec detail**: Low — what and why, not how

Observations are grouped by theme, deduplicated, and prioritized. The output is a set of backlog items that describe user-visible outcomes, not implementation steps.

### 3. Workplan
**Role**: Planner (today: human + AI, future: planning agent)
**Input**: Backlog items selected for a work cycle
**Output**: Milestones with draft tasks, dependency sketch, execution ordering
**Spec detail**: Medium — task descriptions capture intent and rough scope

The planner decomposes backlog items into implementable tasks. This is where:
- Shared foundations are discovered (e.g., "we need a reusable component before touching any page")
- Dependencies emerge (context must exist before consumers)
- New tasks appear that don't map to any backlog item (enablers)
- Execution order is determined

**The planner decides *what* to do.** Task descriptions are intent-level — good enough to understand scope, not detailed enough to implement from.

### 4. Review (spec authoring)
**Role**: Reviewer (today: human + AI, future: workplan review agent)
**Input**: Draft tasks + codebase access
**Output**: Detailed specs, acceptance criteria, verified dependencies, tasks moved to `todo`
**Spec detail**: High — files, changes, interfaces, testable conditions

**This is where the spec gets written.** The reviewer:
1. Reads the codebase to verify task assumptions
2. Identifies stale references, false premises, missing dependencies
3. Authors detailed specs with file paths, interface contracts, code patterns
4. Writes testable acceptance criteria (future: SHALL + GIVEN/WHEN/THEN format)
5. Sets dependencies and execution order
6. Creates quality gate task for the milestone
7. Moves enriched tasks to `todo`

**The reviewer decides *how* to specify it precisely.** Spec quality at this stage directly determines executor success rate.

See: [Workplan Review Protocol](workplan-review-PROTOCOL.md)

### 5. Execution
**Role**: Executor (today: vtf-executor subagent, future: vafi executor agent)
**Input**: `todo` task with detailed spec
**Output**: Code + tests + commit on task branch
**Spec detail**: N/A — consumes spec, does not author it

The executor implements exactly what the spec says. It does not make design decisions, question the workplan structure, or modify scope. If the spec is wrong, that's a reviewer failure.

See: [Simulation Protocol](guides/simulation-protocol-GUIDE.md)

### 6. Verification
**Role**: Judge (today: vtf-judge subagent, future: vtf-judge agent)
**Input**: Completed task + spec + executor report
**Output**: Verdict (pass/fail with evidence)
**Spec detail**: N/A — verifies against spec

The judge runs tests, reviews code against the spec, checks blast radius, and produces a structured verdict. It does not modify code or make design decisions.

## Role Separation

| Role | Decides | Does NOT |
|------|---------|----------|
| **Human** | What matters, priorities, product direction | Write specs, implement, verify |
| **Planner** | What to do, task decomposition, ordering | How to specify it, implementation details |
| **Reviewer** | How to specify precisely, what's accurate vs stale | Implementation, verification |
| **Executor** | Implementation choices within spec bounds | Design decisions, scope changes |
| **Judge** | Whether implementation meets spec | Code modifications, design decisions |

## Key Design Principle

> Invest more in the review agent than the executor agent. The reviewer's spec quality directly determines the executor's success rate.

Evidence: The Navigation & Breadcrumbs milestone (2026-03-26) achieved zero rework cycles across 6 implementation tasks because the review phase produced detailed, codebase-verified specs with code snippets, file paths, and testable acceptance criteria.

## Related Documents

- [Workplan Review Protocol](workplan-review-PROTOCOL.md) — the formalized review process (stage 4)
- [Simulation Protocol](guides/simulation-protocol-GUIDE.md) — the execution process (stages 5-6)
- [Backlog-to-Execution Gap Analysis](backlog-to-execution-gap-ANALYSIS.md) — the problem analysis that led to this pipeline
- [Breadcrumbs Retrospective](simulation-breadcrumbs-RETROSPECTIVE.md) — first application, lessons learned
- SDD Spec Format Research (backlog task EBViakmvP4zYqiL3-2gbR) — formalizing the spec format with OpenSpec-inspired structure
