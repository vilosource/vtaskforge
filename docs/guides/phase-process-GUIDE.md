# vtaskforge — Phase Execution Process Guide

Status: Draft (2026-03-20)
Iteration: 0 (pre-Phase 1, based on Phase 0 findings)

This guide defines how phases are planned, executed, and verified. It is a living document — each phase execution produces findings that improve the process for the next phase.

## Roles

| Role | Who | Responsibility |
|---|---|---|
| Supervisor | Human | Writes task specs, dispatches agents, final review authority |
| Executor | Sonnet subagent | Implements task per spec, reports completion |
| Judge | Opus agent | Evaluates behavioral spec against implementation, produces verdicts |

## Task Spec Template

Every task in a phase follows this structure:

```yaml
id: <phase>.<sequence>
name: "<short name>"
depends_on: [<task-ids>]
agent_model: sonnet  # or opus for complex reasoning tasks
isolation: worktree  # or sequential (see Git Isolation Rules)

description: |
  <What this task accomplishes and why>

files:
  create:
    - path/to/new/file.py  # exact paths
  modify:
    - path/to/existing/file.py

implementation:
  approach: |
    <How to implement — specific enough for Sonnet>
    <Include code patterns, imports, Django conventions to follow>
  constraints:
    - <hard constraints the agent must follow>
    - <e.g., "use DRF ModelSerializer, not manual serialization">
  references:
    - <existing files to read for context or patterns>

acceptance_criteria:
  - <concrete, verifiable criterion with verification command>
  - "pytest tests/test_foo.py passes"
  - "curl http://localhost:8000/v1/foo returns 200"

behavioral_spec:
  id: <spec-id>
  priority: high
  behaviors:
    - "<plain-language behavior — intent, not implementation>"
    - "POST /v1/tasks with valid JSON returns 201 and includes id in response"
    - "GET /v1/tasks/{id} for non-existent id returns 404 with JSON error body"

test_command: "pytest tests/test_<relevant>.py"
```

### Spec Detail Calibration

Sonnet needs more prescriptive specs than Opus. The spec must include:

- **Exact file paths** to create or modify
- **Code patterns** to follow (e.g., "use DRF APIView" not just "create an endpoint")
- **Imports and dependencies** when non-obvious
- **Verification commands** to run after implementation
- **References** to existing files that demonstrate the project's conventions

The spec should NOT include:
- Full code listings (Sonnet can implement from patterns + constraints)
- Step-by-step shell commands (Sonnet can figure out tooling)
- Explanations of Django/DRF basics (Sonnet knows these)

### Behavioral Spec Writing Rules

Behaviors describe **what the system does**, not how it's built:
- Good: "GET /v1/health returns 200 with JSON body containing status field"
- Bad: "views.py has a class HealthView that inherits from APIView"

Behaviors should be:
- **Independent** — each behavior is verifiable on its own
- **Observable** — can be checked via HTTP, shell command, or code inspection
- **Intent-based** — describe expected outcome, not implementation detail

## Execution Flow

```
1. Supervisor writes task spec + behavioral spec
2. Supervisor dispatches Sonnet subagent with task spec
3. Sonnet executes, commits to worktree (or main branch if sequential)
4. Gate 1 — Mechanical checks:
   - Run test_command (pytest)
   - Run acceptance criteria verification commands
   - If any fail → back to Sonnet with failure details
5. Gate 2 — Judge evaluation:
   - Opus judge agent receives behavioral spec + access to code
   - Judge probes running service, reads code, produces verdicts
   - All pass → proceed to human review
   - Any fail → back to Sonnet with verdict details
6. Gate 3 — Human review:
   - Supervisor reviews judge verdicts + code diff
   - Approve → merge worktree, move to next task
   - Reject → back to Sonnet with feedback
   - Request changes → specific feedback, Sonnet re-executes
```

### Gate Details

**Gate 1 (Mechanical)** is cheap and fast. It catches obvious failures before wasting judge tokens. The test_command field defines what runs here. If the task has no tests yet (e.g., scaffolding tasks), this gate is skipped.

**Gate 2 (Judge)** is the automated review. The judge agent:
- Receives: behavioral spec YAML, repo path, running service URL (if applicable)
- Produces: structured verdict per behavior (pass/fail + reasoning + evidence + code refs)
- Does NOT: make design decisions, suggest improvements, or block on style

**Gate 3 (Human)** focuses on what machines can't verify:
- Does the approach fit the architecture?
- Are there edge cases the spec missed?
- Is the code maintainable?
- Should the spec be updated?

## Git Isolation Rules

### When to use worktree isolation

Use `isolation: "worktree"` when:
- Multiple tasks can run in parallel (no dependency between them)
- Tasks create new files that don't overlap

### When to use sequential execution

Use sequential execution (no isolation) when:
- Task modifies shared files (urls.py, settings.py, existing models)
- Task depends on migrations from a previous task
- Task modifies files that a parallel task also modifies

### Merge Strategy

After worktree tasks complete and pass all gates:
1. Supervisor merges worktree branches one at a time
2. If merge conflicts arise, supervisor resolves (not the agent)
3. Re-run Gate 1 after merge to verify nothing broke

## Failure Handling

| Failure point | Action |
|---|---|
| Sonnet can't complete task | Check if spec is detailed enough. Add implementation hints or escalate to Opus. |
| Gate 1 fails (tests) | Send failure output back to same Sonnet agent. Allow 1 retry. If retry fails, escalate. |
| Gate 2 fails (judge) | Send verdict details back to Sonnet. If judge identifies a spec error, supervisor updates spec first. |
| Gate 3 fails (human) | Supervisor provides specific feedback. Sonnet re-executes with feedback appended to spec. |
| Merge conflict | Supervisor resolves manually. Re-run Gate 1. |

### Escalation

"Escalate" means:
1. Re-dispatch same task to Opus instead of Sonnet
2. OR add more detail to the spec and retry with Sonnet
3. Never brute-force retry without understanding the failure

## Spec Deviation Protocol

When an executor agent deviates from the spec (e.g., changes a port, adds a missing dependency):
- Agent must document the deviation in its completion output
- Judge agent flags deviations as part of its verdict
- Supervisor decides: accept deviation and update spec, or reject and enforce original spec
- Accepted deviations feed back into the implementation plan for consistency

## Phase Retrospective

After each phase completes, document:

1. **What worked** — process elements that should be kept
2. **What didn't work** — failures, friction, wasted time
3. **Spec quality** — were specs detailed enough? Too detailed?
4. **Gate effectiveness** — did each gate catch real issues? False positives?
5. **Model performance** — did Sonnet handle the tasks? Which needed escalation?
6. **Process changes** — concrete changes to this guide for the next phase

Append retrospective findings to this document as versioned iterations.

---

## Iteration Log

### Iteration 0 — Pre-Phase 1 (2026-03-20)

Based on Phase 0 dry run findings (see `phase0-findings-ANALYSIS.md`):

- **Issue #1 (Port exposure):** Specs must trace dependency chains. Added constraints field to task template.
- **Issue #2 (No git isolation):** Added Git Isolation Rules section with worktree vs sequential guidance.
- **Issue #3 (Spec errors):** Added Spec Deviation Protocol. Agents must flag deviations, not silently fix.
- **Issue #4 (Agent capability):** Defaulted to Sonnet executors with calibrated spec detail. Opus reserved for judge and escalation.
- **Issue #5 (Pyright):** No process change needed. Dev tooling concern.
- **Issue #6 (Review discipline):** Added three-gate verification flow (mechanical → judge → human). Review is structured, not ad-hoc.

### Iteration 1 — Post-Phase 1 (2026-03-20)

Phase 1 executed 12 tasks sequentially with Sonnet executors. 568 tests, 0 retries, 2 minor spec deviations, 1 cross-task regression. Full findings in `phases/phase1/execution-LOG.md`.

#### What worked

1. **Sonnet handled everything.** Zero escalations to Opus. Every task completed on first attempt. The spec detail level (file paths + code patterns + constraints, but NOT full code listings) was the sweet spot for Sonnet.

2. **Spec deviation protocol.** Agents self-reported deviations clearly (unclaim bypassing state machine, target_type max_length increase). This made review fast — supervisor could assess the deviation without hunting for it.

3. **Sequential execution eliminated merge conflicts.** Phase 0 had a near-miss with parallel agents. Phase 1's strict sequential ordering meant zero merge conflicts and zero coordination overhead. The speed cost was acceptable for 12 tasks.

4. **Behavioral specs were useful for judge evaluation.** The state machine judge run (task 1.5) proved the transition table matched the design doc — something unit tests alone can't verify. The curl-based judge on task 1.1 caught formatting details and edge cases.

5. **Task spec template worked.** The YAML structure (description + files + implementation + constraints + references + behavioral_spec) gave agents everything they needed. No agent asked for clarification.

6. **Tests as the primary gate.** Gate 1 (mechanical) caught the one real issue — the cross-task regression in 1.12. Fast, cheap, reliable.

#### What didn't work

1. **Cross-task regressions.** Task 1.12 changed claim behavior (422 → 409) but didn't update a test from task 1.10 that depended on the old behavior. The spec told 1.12 to update tests in `test_lifecycle.py` but missed `test_auto_logging.py`. **Root cause:** specs only listed files the agent should create/modify — they didn't account for files created by OTHER tasks that might be affected.

2. **Judge was wasteful on CRUD tasks.** Tasks 1.2, 1.3, 1.7, 1.8 followed identical DRF patterns. Running a judge agent on these added ~75s per task with zero new findings. The mechanical tests were sufficient.

3. **Design doc gap surfaced late.** The unclaim transition (doing → todo) wasn't in the state machine's VALID_TRANSITIONS. The Sonnet agent on task 1.6 discovered this and worked around it, but ideally the spec or design review would have caught it earlier.

4. **Dead code pattern repeated.** Every viewset had an unreachable `update()` override alongside `http_method_names` that already excluded PUT. Not a bug, but unnecessary code proliferated across 5+ viewsets because the first task established the pattern and subsequent tasks copied it.

5. **Gate 3 (human review) was rubber-stamped.** The supervisor auto-approved everything after Gate 1 passed. This mirrors the Phase 0 finding about review discipline — without enforcement, human review degrades. The behavioral judge partially compensates, but only when run.

#### Spec quality assessment

- **Detail level: right.** Sonnet-calibrated specs (file paths, field definitions, code patterns) worked. No task needed more detail, and no spec was so detailed it constrained the agent unnecessarily.
- **Behavioral specs: useful but underutilized.** Only 2 of 12 tasks got judge evaluation. The specs were well-written but most were verified only through tests.
- **Missing: impact analysis.** Specs listed files to create/modify but not files that might be AFFECTED by the change. Task 1.12 needed to know about test_auto_logging.py (created by 1.10) to update it.
- **Missing: error code contracts.** The claim action's error codes (409 vs 422) weren't formally specified until task 1.12, which changed what 1.6 had established. Error response contracts should be defined upfront.

#### Gate effectiveness

| Gate | Runs | Caught issues | False positives | Assessment |
|---|---|---|---|---|
| Gate 1 (Mechanical) | 12 | 1 regression | 0 | Essential — the primary safety net |
| Gate 2 (Judge) | 2 | 0 (confirmed correctness) | 0 | Valuable for core logic, wasteful for CRUD |
| Gate 3 (Human) | 0 (auto-approved) | 0 | 0 | Not exercised — process gap |

#### Process changes for next phase

1. **Add "affected_files" to task spec template.** Beyond create/modify, specs should list files created by prior tasks that might need updating. This catches cross-task regressions at spec time.

2. **Tiered judge policy.** Run judge on:
   - Tasks tagged `priority: high` or `core: true`
   - Tasks that modify code created by other tasks
   - The first task establishing a new pattern
   Skip judge on CRUD pattern-repeat tasks where Gate 1 tests cover all behaviors.

3. **Error code contracts in specs.** When a task defines error responses (status codes + error codes), document them as a contract. Subsequent tasks that modify the same endpoint must reference and update the contract.

4. **Regression test sweep.** After modifying behavior established by a prior task, the executor agent must grep for tests referencing the changed behavior across ALL test files, not just its own.

5. **Design review gate before execution.** Add a pre-execution step: before dispatching task specs, review them against the design doc for completeness. The unclaim gap (doing → todo) should have been caught here.

6. **Pattern templates.** The DRF CRUD pattern (model + serializer + viewset + urls + tests) was repeated 5 times. Create a reusable pattern template that agents follow, eliminating the dead code propagation issue.
