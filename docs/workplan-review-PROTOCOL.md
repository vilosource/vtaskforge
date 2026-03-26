# Workplan Review Protocol: Draft to Ready

## Purpose

This protocol defines how a workplan/milestone moves from `draft` to `todo` — the review process that ensures tasks are executable before any executor touches them.

**Role**: Workplan Reviewer (today: human + AI, future: dedicated review agent)
**Input**: A workplan/milestone with tasks in `draft` status
**Output**: Tasks with detailed specs, enriched and moved to `todo`, or flagged with issues

---

## Where This Fits: The Execution Pipeline

Work flows through a pipeline of stages, each with a distinct role and output. Spec authoring happens at the **review stage** — not during planning, not during execution.

```
Observation → Backlog → Workplan → Review (this protocol) → Execution → Verification
```

| Stage | Role | Input | Output | Spec Detail Level |
|-------|------|-------|--------|-------------------|
| **Observation** | Human | User need or pain point | Short description ("breadcrumbs are inconsistent") | None — intent only |
| **Backlog** | Human + Planner | Observations, priorities | Scoped work item with goal and context | Low — what and why |
| **Workplan** | Planner | Backlog items | Milestones, draft tasks, dependency sketch, ordering | Medium — task descriptions, rough scope |
| **Review** | **Reviewer (this protocol)** | Draft tasks + codebase access | **Detailed specs, AC, verified dependencies** | **High — files, changes, interfaces, GIVEN/WHEN/THEN** |
| **Execution** | Executor | Todo task with spec | Code + tests + commit | N/A — consumes spec |
| **Verification** | Judge | Completed task + spec | Verdict (pass/fail) | N/A — verifies against spec |

### Key design decisions

**The planner decides *what* to do.** It decomposes backlog items into tasks, sets ordering and dependencies, and writes descriptions that capture intent. Planner output is rough — good enough to understand scope, not detailed enough to implement from.

**The reviewer decides *how* to specify it.** It reads the codebase, verifies assumptions, and produces detailed specs with file paths, interface contracts, code patterns, and testable acceptance criteria. The reviewer's spec quality directly determines executor success rate (breadcrumbs milestone: zero rework with well-specified tasks).

**The executor never questions the spec.** It implements exactly what the spec says. If the spec is wrong, that's a reviewer failure, not an executor failure. This clean separation means we can invest in spec quality (the review agent) independently of execution capability (the executor agent).

---

## Roles

| Role | Responsibility | Today | Future |
|------|---------------|-------|--------|
| **Planner** | Decomposes backlog items into workplans, milestones, draft tasks with intent-level descriptions | Human + AI | Planning agent |
| **Reviewer** | Verifies against codebase, authors detailed specs, enriches to ready state | Human + AI (this protocol) | Workplan review agent |
| **Executor** | Picks up `todo` tasks, implements per spec, submits | Human + AI (simulated) | vafi executor agent |
| **Judge** | Verifies completed work against spec and AC | Human + AI | vtf-judge agent |

The planner writes what and why. The reviewer writes how (the spec). The executor implements. The judge verifies. No role does another role's work.

---

## Protocol Steps

### Phase 1: Understand the Goal

1. Read the workplan and milestone description
2. Read the implementation plan artifact (if one exists — check `kb wsa list` or task notes)
3. Identify the **done state** — what does the milestone deliver when all tasks complete?
4. Note the intended execution order and any parallelism

**Gate**: Can you state the milestone goal in one sentence? If not, the workplan needs clarification before proceeding.

### Phase 2: Codebase Verification

For each task, verify that its assumptions match the current state of the code. This is the most critical phase — specs based on false premises cause rework.

1. **File existence** — Do the referenced files exist? Have they been renamed or moved?
2. **Code state** — Do the specific patterns/components/lines described still exist as described?
3. **Route structure** — Do URL patterns and route definitions match what the task assumes?
4. **Data availability** — Are the APIs, hooks, and data shapes the task depends on actually available?
5. **Dependency state** — Are prerequisite packages/components already in place or do they need creating?

**Execution pattern**: Run verification agents in parallel, one per task or logical group. Each agent explores the codebase read-only and produces a structured report.

**Output per task**: A verification report noting:
- Confirmed assumptions (with evidence: file path, line, snippet)
- Stale/incorrect assumptions (with current state)
- Unknown/unverifiable assumptions (need investigation)

**Gate**: All critical assumptions verified. Stale references corrected. No task is based on false premises.

### Phase 3: Structure Assessment

Evaluate the workplan as a whole. This phase may produce structural changes (splits, merges, new tasks).

1. **Cohesion** — Does every task contribute to the milestone goal? Are there missing tasks?
2. **Decomposition** — Is each task a single logical unit of work? Flag tasks that bundle unrelated changes. Rule of thumb: if a task creates foundational pieces AND consumes them across multiple files, split it.
3. **Dependencies** — Map the dependency graph. Identify tasks that must complete before others can start.
4. **Risk ordering** — Which task, if it fails, blocks the most others? Foundational tasks execute first.
5. **Blast radius** — Which tasks touch the most files? These carry higher regression risk and may need tighter gates.
6. **Quality gate** — Does the milestone end with a quality gate task? Per the [simulation protocol](guides/simulation-protocol-GUIDE.md), every milestone must have one. The gate task depends on ALL other tasks in the milestone, runs the full test suite, and verifies the milestone checklist. If missing, create it.

**Structural actions** (applied immediately, not deferred):
- **Split** overloaded tasks — create new tasks via vtf, move scope from the original
- **Merge** tasks that are too small to stand alone
- **Create** missing tasks discovered during verification
- **Cancel** tasks whose assumptions were invalidated

**Output**: Dependency graph and execution order. All structural changes applied to vtf.

**Gate**: No overloaded tasks. Dependency graph is explicit and acyclic. Execution order is clear.

### Phase 4: Task Enrichment

For each task, ensure it meets the **executor readiness bar** — an executor should be able to pick up the task cold and succeed without asking questions.

#### Required fields

| Field | What goes in it | Common mistakes |
|-------|----------------|-----------------|
| **Description** | Clear summary of what and why. References current code state. | Stale line numbers, vague scope |
| **Spec** | Implementation detail: files to create/modify (with paths), what to change (by pattern/component name, not line number), interface contracts (types, props, signatures), edge cases | Too terse ("fix the links"), or referencing plan artifact without inlining the relevant parts |
| **Acceptance criteria** | Observable, verifiable conditions. Format: "AC1: description" | Missing entirely, or restating the description |
| **Dependencies** | Documented in spec as "Depends On: task title" | Not documented at all — executor starts before foundation exists |
| **Test command** | At minimum: build + existing tests | Missing — no build gate |
| **Labels** | Accurate categorization | Stale labels from before restructuring |

#### Spec structure template

```markdown
# Task Title

## Overview
One paragraph: what this task does and why.

## Depends On
- Task title (brief description of what it provides)

## Changes

### `path/to/file.tsx` (NEW|MODIFY)
- What to add/change, described by component/pattern name
- Interface contracts with types
- Code snippets for non-obvious parts

### `path/to/another.tsx` (MODIFY)
- ...

## Verification
- Build command and expected result
- Test command and expected result
- Manual verification steps (if applicable)

## Acceptance Criteria
- AC1: ...
- AC2: ...
```

#### Acceptance criteria guidelines

Good AC is **observable and falsifiable**:
- "AC1: Sidebar highlights correct project when viewing `/tasks/:id`" (testable)
- NOT: "AC1: Sidebar works correctly" (vague)

Include both positive and negative cases:
- "AC4: Handles missing milestone gracefully (no crash, segment omitted)"

Always include a build/test gate:
- "AC-last: `npm run build` and `npm test` pass"

#### Optional but recommended fields
- **`judge: true`** — Set if the task output should be reviewed by a judge agent before completion (recommended for foundational tasks)
- **`test_command`** — vtf field for automated verification (when available)

**Gate**: For each task, ask: "Could an executor pick this up cold and succeed without asking questions?" If no, the task isn't ready.

### Phase 5: Transition to Todo

1. Apply all enrichments via `vtf_manage_task(action=update)`
2. Move each task to `todo` via `vtf_manage_task(action=submit)` (note: vtf action is `submit`, not `todo`)
3. Verify the board via `vtf_board_overview` — correct count in `todo`
4. Record any open questions or risks as task notes

---

## vtf State Machine Reference

```
draft --[submit]--> todo --[claim]--> doing --[submit_work]--> pending_completion_review --[approve]--> done
                                        |                              |
                                        +--[block]--> blocked          +--[request_changes]--> doing
```

Key transitions for this protocol:
- `draft → todo`: action = `submit`
- Tasks can also go `draft → cancelled` or `draft → deferred`
- `update` action modifies task fields without changing status

---

## Dependency Management

vtf has a `requires` field on tasks for system-enforced blocking. However, as of this writing, dependencies are documented in the spec as prose ("Depends On: ...") rather than using `requires` task IDs. This is a known gap.

**Current approach**: Document dependencies in spec text. Execution order is managed by the reviewer/supervisor, not enforced by vtf.

**Future approach**: When vtf dependency enforcement is implemented, set `requires` field with task IDs during Phase 4.

---

## Anti-patterns

| Anti-pattern | Why it's bad | What to do instead |
|---|---|---|
| Skipping codebase verification | Specs based on stale code cause rework | Always verify before enriching |
| No acceptance criteria | Executor doesn't know "done", judge can't verify | Write observable, falsifiable AC |
| No dependencies documented | Executor picks up task before foundation exists | Document in spec, enforce via execution order |
| Overloaded tasks | Multiple failure modes, hard to review, blocks parallelism | Split: foundation vs consumers |
| Line number references | Lines shift with every commit | Reference by component/pattern name |
| Assuming data availability | "Data is already available" without verification | Verify hooks/props/API responses exist |
| Copying plan artifact verbatim | Plan may be outdated, executor needs current truth | Inline relevant parts, verify against code |

---

## Lessons Learned

### From: Navigation & Breadcrumbs workplan (2026-03-26)

**First application of this protocol. Key findings:**

1. **Parallel verification is essential** — 4 agents checking assumptions simultaneously caught a false claim ("data already available from parent context") that would have caused rework during implementation.

2. **Task decomposition matters more than you think** — Original Task 1 bundled 4 distinct pieces (create context, create component, wire provider, migrate 3 pages). Splitting into foundation + migration made each independently executable and testable.

3. **Specs must be self-contained** — An implementation plan artifact existed but wasn't linked to individual tasks. The executor needs everything in the task spec — referencing an external plan adds a lookup step and the plan may be stale.

4. **vtf's action vocabulary differs from status names** — The transition from `draft` to `todo` uses action `submit`, not `todo`. The protocol must use vtf's actual API vocabulary.

5. **Dependencies need dual documentation** — Prose in the spec ("Depends On: foundation task") for human readability, plus vtf `requires` field (when supported) for system enforcement. Neither alone is sufficient.

6. **Quality gate task is a structural requirement, not an afterthought** — The simulation protocol requires every milestone to end with a quality gate task. Phase 3 initially missed this check, meaning we almost moved to execution without a full regression gate. Added as Phase 3 step 6.

7. **Verification agents should be read-only** — The Phase 2 agents explored the codebase but made no changes. This is the right boundary: read to verify, then act to enrich. Mixing the two risks making changes based on incomplete understanding.

---

## Checklist Summary

```
Phase 1: Understand the Goal
  [ ] Workplan/milestone description read
  [ ] Implementation plan artifact read (if exists)
  [ ] Done-state articulated in one sentence
  [ ] Execution order noted

Phase 2: Codebase Verification
  [ ] Verification agents dispatched (parallel, read-only)
  [ ] All task assumptions verified against current code
  [ ] False/stale assumptions identified and noted
  [ ] Verification reports reviewed

Phase 3: Structure Assessment
  [ ] Cohesion check — all tasks contribute to goal
  [ ] Decomposition check — no overloaded tasks
  [ ] Dependency graph mapped
  [ ] Quality gate task exists for the milestone
  [ ] Structural changes applied (splits/merges/creates/cancels)

Phase 4: Task Enrichment
  [ ] Every task has accurate description
  [ ] Every task has self-contained spec (files, changes, contracts)
  [ ] Every task has observable acceptance criteria
  [ ] Every task has dependencies documented
  [ ] Every task has verification/test steps
  [ ] Executor readiness test passed: "could an executor pick this up cold?"

Phase 5: Transition to Todo
  [ ] All enrichments applied via vtf update
  [ ] All tasks submitted (draft → todo) via vtf submit
  [ ] Board verified — correct task count in todo
  [ ] Open questions recorded as task notes
```
