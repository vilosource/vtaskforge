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
