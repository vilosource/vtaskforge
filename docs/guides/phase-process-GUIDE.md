# vtaskforge — Phase Execution Process Guide

Status: Active (2026-03-20)
Iteration: 2 (post-Phase 1 deep retrospective)

This guide defines how phases are planned, executed, and verified. It is a living document — each phase execution produces findings that improve the process for the next phase.

## Roles

| Role | Who | Responsibility |
|---|---|---|
| Supervisor | Human or orchestrating agent | Writes task specs, dispatches agents, final review authority |
| Executor | Sonnet subagent | Implements task per spec, reports completion and deviations |
| Judge | Opus agent | Code review against design docs, pattern compliance, contract verification |

## Task Spec Template

Every task in a phase follows this structure:

```yaml
id: <phase>.<sequence>
name: "<short name>"
depends_on: [<task-ids>]
agent_model: sonnet  # or opus for complex reasoning tasks
isolation: worktree  # or sequential (see Git Isolation Rules)
judge: true          # or false (see Judge Policy)

description: |
  <What this task accomplishes and why>

files:
  create:
    - path/to/new/file.py
  modify:
    - path/to/existing/file.py
  affected:
    - path/to/file/created/by/prior/task.py  # files that may need updating
    - tests/other_app/test_something.py       # tests that reference changed behavior

contracts:
  establishes:
    - name: "claim-error-response"
      description: "POST /v1/tasks/{id}/claim on non-todo task returns 409 ALREADY_CLAIMED"
  modifies:
    - name: "claim-error-response"  # must update all tests/consumers of this contract
  depends_on:
    - name: "task-state-machine"    # references contract established by another task

implementation:
  approach: |
    <How to implement — specific enough for Sonnet>
    <Include code patterns, imports, Django conventions to follow>
  pattern: "drf-crud"  # reference to pattern template (see Pattern Templates)
  constraints:
    - <hard constraints the agent must follow>
  references:
    - <existing files to read for context or patterns>

acceptance_criteria:
  - <concrete, verifiable criterion with verification command>

behavioral_spec:
  id: <spec-id>
  priority: high
  behaviors:
    - "<plain-language behavior — intent, not implementation>"

test_command: "pytest tests/test_<relevant>.py"
```

### Spec Fields Added in Iteration 2

**`files.affected`** — Files created by prior tasks that may need updating when this task changes behavior. The executor agent MUST grep these files for references to changed behavior and update them. This prevents cross-task regressions.

**`contracts`** — Formal contracts this task establishes, modifies, or depends on. A contract is a named behavioral guarantee (error codes, state transitions, event emissions). When a task modifies a contract, it must update all downstream consumers. See Contract-Driven Specs.

**`judge`** — Whether this task requires judge evaluation. See Judge Policy.

**`implementation.pattern`** — Reference to a pattern template. See Pattern Templates.

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

## Contract-Driven Specs

Contracts are named behavioral guarantees that tasks establish. They solve the cross-task regression problem by making dependencies on behavior explicit.

### What is a contract?

A contract is a named, versioned guarantee about how a piece of the system behaves:

```yaml
# Example: established by task 1.6
- name: "task-claim-endpoint"
  type: error_contract
  endpoint: "POST /v1/tasks/{id}/claim"
  guarantees:
    - "Returns 200 with task data on successful claim"
    - "Returns 400 VALIDATION_ERROR if agent_id missing"
    - "Returns 409 ALREADY_CLAIMED if task not in todo status"
    - "Returns 422 INVALID_TRANSITION for state machine violations"
```

### Contract types

| Type | What it guarantees | Example |
|---|---|---|
| error_contract | HTTP status codes and error codes for an endpoint | "claim returns 409 ALREADY_CLAIMED" |
| state_contract | What state transitions an action causes | "submit routes to pending_start_review or todo" |
| event_contract | What events are emitted by an action | "claim creates a 'claimed' TaskEvent" |
| data_contract | Response shape and field guarantees | "task response includes claimed_by, claimed_at" |

### How contracts prevent regressions

1. Task 1.6 establishes `task-claim-endpoint` contract
2. Task 1.10 writes tests against that contract (tests reference the 409 status code)
3. Task 1.12 modifies the `task-claim-endpoint` contract
4. Because 1.12's spec says `contracts.modifies: task-claim-endpoint`, the agent knows to grep for all references to the old contract and update them

### Where contracts live

Contracts are documented in each task's spec file. A future improvement is to extract them into a shared `contracts/` directory, but for now inline is sufficient.

## Execution Flow

```
1. Supervisor writes task spec + behavioral spec + contracts
2. Supervisor dispatches Sonnet subagent with task spec
3. Sonnet executes, commits
4. Gate 1a — Task-specific tests:
   - Run test_command (pytest for this task's tests)
   - If fail → back to Sonnet with failure details
5. Gate 1b — Full suite regression:
   - Run pytest tests/ (entire test suite)
   - If fail → agent must fix regressions (check files.affected)
6. Gate 2 — Judge code review (if judge: true):
   - Opus judge reads code + design docs
   - Verifies: design alignment, pattern compliance, contract maintenance
   - Does NOT re-test behaviors (tests do that)
   - Produces structured verdict
7. Approve → move to next task
```

### Gate Details

**Gate 1a (Task tests)** — fast feedback. Runs only the task's test_command. Catches implementation bugs immediately.

**Gate 1b (Full suite)** — regression detection. Runs the entire test suite. Catches cross-task breakage. This gate is mandatory — Phase 1's regression was only caught because it was run. If Gate 1b fails, the executor agent must check `files.affected` and fix tests it broke.

**Gate 2 (Judge code review)** — design alignment. The judge is a code reviewer, NOT a behavior tester. Tests verify behavior. The judge verifies:
- Does the implementation match the design doc's intent?
- Does the code follow the established pattern (or introduce dead code)?
- Are there N+1 queries, missing indexes, or architectural issues?
- Are contracts maintained — if this task modifies a contract, did it update all consumers?
- Does the code match the referenced pattern template?

The judge does NOT:
- Re-test behaviors via curl (tests already proved this)
- Make design decisions or suggest improvements
- Block on code style preferences

### Judge Policy

Run the judge (`judge: true`) on:
- Tasks that establish a new pattern (the first CRUD task, the first nested endpoint)
- Tasks that modify core logic (state machine, review policy, claim logic)
- Tasks that modify code or contracts established by other tasks
- Tasks tagged `priority: high`

Skip the judge (`judge: false`) on:
- CRUD pattern-repeat tasks where Gate 1 tests cover all behaviors
- Model-only tasks with no API surface
- Scaffolding tasks (file creation, migrations only)

## Pattern Templates

Pattern templates are canonical implementations of repeated structures. Agents reference them instead of copying from prior tasks, preventing dead code propagation.

Pattern templates live in `docs/patterns/` and describe:
- The canonical file structure
- The correct implementation approach (no dead code)
- Common mistakes to avoid
- Test patterns to follow

### Available Patterns

#### drf-crud

Standard DRF model + serializer + viewset + urls + tests.

```
When to use: Any new Django app with REST CRUD endpoints.

Model:
- Inherit from NanoIDMixin + TimestampMixin (from core.mixins)
- Define STATUS_CHOICES as a list of tuples
- Add __str__ returning the name/title field

Serializer:
- ModelSerializer with fields = "__all__" or explicit list
- id, created_at, updated_at as read_only_fields

ViewSet:
- ModelViewSet
- Disable PUT by setting: http_method_names = ["get", "post", "patch", "delete", "head", "options"]
- Do NOT add a separate update() override — http_method_names is sufficient
- Custom status-change actions as @action(detail=True, methods=["post"])
- Validate current status before changing (return 400 for invalid transitions)

URLs:
- DefaultRouter, register viewset with app name prefix
- Wire into vtaskforge/urls.py: path("v1/", include("<app>.urls"))

Tests:
- Use shared fixtures from conftest.py (see test-fixtures pattern)
- Model tests: creation, defaults, str, nanoid pk, cascade deletes
- API tests: CRUD operations, status transitions, error cases
```

#### nested-endpoint

Append-only nested resources under a parent (e.g., /tasks/{id}/notes).

```
When to use: Resources that belong to a parent and are append-only (notes, reviews, events).

ViewSet:
- Use CreateModelMixin + ListModelMixin + GenericViewSet (NOT ModelViewSet)
- Override get_queryset() to filter by parent_id from URL kwargs
- Override perform_create() to set parent from URL kwargs
- Return 404 if parent doesn't exist
- Do NOT register update, partial_update, or destroy

URLs:
- Manual path (not router): path("<parent>/<str:parent_id>/<resource>/", View.as_view({...}))
```

#### test-fixtures

Shared test infrastructure for consistent, maintainable tests.

```
When to use: All test files.

conftest.py (tests/ root):
- Fixture: api_client — DRF APIClient instance
- Fixture: workplan — creates a default Workplan
- Fixture: phase — creates a Phase under workplan
- Fixture: task — creates a Task under phase (status=draft)
- Fixture: todo_task — creates a Task with status=todo
- Fixture: doing_task — creates a claimed Task with status=doing

Use factory_boy for complex entity creation. Define factories in tests/factories.py.
```

## Git Isolation Rules

### When to use worktree isolation

Use `isolation: "worktree"` when:
- Multiple tasks can run in parallel (no dependency between them)
- Tasks create files in different app directories
- Tasks do NOT both modify the same shared file (urls.py, settings.py)

### When to use sequential execution

Use sequential execution (no isolation) when:
- Task modifies shared files (urls.py, settings.py, existing models)
- Task depends on migrations from a previous task
- Task modifies files that a parallel task also modifies

### Identifying parallel opportunities

Map each task's create/modify files. If two tasks have zero file overlap, they can be parallel with worktree isolation. The only structural shared file is typically `vtaskforge/urls.py` — tasks that only add new apps need to add a single include line here.

### Merge Strategy

After worktree tasks complete and pass all gates:
1. Supervisor merges worktree branches one at a time
2. If merge conflicts arise, supervisor resolves (not the agent)
3. Re-run Gate 1b (full suite) after merge to verify nothing broke

## Failure Handling

| Failure point | Action |
|---|---|
| Sonnet can't complete task | Check if spec is detailed enough. Add implementation hints or escalate to Opus. |
| Gate 1a fails (task tests) | Send failure output back to same Sonnet agent. Allow 1 retry. If retry fails, escalate. |
| Gate 1b fails (regression) | Agent checks files.affected, greps for changed behavior in all test files, fixes. 1 retry. |
| Gate 2 fails (judge) | If design misalignment: supervisor updates spec. If pattern violation: agent fixes. |
| Merge conflict | Supervisor resolves manually. Re-run Gate 1b. |

### Escalation

"Escalate" means:
1. Re-dispatch same task to Opus instead of Sonnet
2. OR add more detail to the spec and retry with Sonnet
3. Never brute-force retry without understanding the failure

## Spec Deviation Protocol

When an executor agent deviates from the spec:
- Agent must document the deviation in its completion output
- Judge agent flags deviations as part of its review
- Supervisor decides: accept deviation and update spec, or reject and enforce original spec
- If the deviation changes a contract, the contract must be updated and all downstream consumers notified
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

## Improvement Roadmap

Improvements are phased based on when they can be applied:

### Do now (before next phase specs)
- [x] Contract-driven specs (added to template)
- [x] Gate 1b full suite regression (added to execution flow)
- [x] Redefine judge as code reviewer (updated gate details)
- [x] Pattern templates (added DRF patterns)

### Do during Phase 2 (learn by doing)
- [ ] Test factory infrastructure (make it an early task, all subsequent tasks use it)
- [ ] Try parallel execution with worktree isolation on independent tasks
- [ ] Validate pattern templates work in practice

### Do when ready (Phase 3+)
- [ ] Design review gate before execution (formalize once enough pattern exists)
- [ ] Dogfooding — import Phase 3 specs into vtaskforge, execute through the system itself
- [ ] Extract contracts into shared contracts/ directory

---

## Iteration Log

### Iteration 0 — Pre-Phase 1 (2026-03-20)

Based on Phase 0 dry run findings (see `phases/phase0/findings-ANALYSIS.md`):

- **Issue #1 (Port exposure):** Specs must trace dependency chains. Added constraints field to task template.
- **Issue #2 (No git isolation):** Added Git Isolation Rules section with worktree vs sequential guidance.
- **Issue #3 (Spec errors):** Added Spec Deviation Protocol. Agents must flag deviations, not silently fix.
- **Issue #4 (Agent capability):** Defaulted to Sonnet executors with calibrated spec detail. Opus reserved for judge and escalation.
- **Issue #5 (Pyright):** No process change needed. Dev tooling concern.
- **Issue #6 (Review discipline):** Added three-gate verification flow (mechanical → judge → human). Review is structured, not ad-hoc.

### Iteration 1 — Post-Phase 1 (2026-03-20)

Phase 1 executed 12 tasks sequentially with Sonnet executors. 568 tests, 0 retries, 2 minor spec deviations, 1 cross-task regression. Full findings in `phases/phase1/execution-LOG.md`.

Key findings:
- Sonnet handled everything. Zero escalations.
- Cross-task regression: task 1.12 changed claim error code (422→409), broke test from task 1.10.
- Judge wasteful on CRUD pattern-repeat tasks, valuable on core logic (state machine).
- Dead code propagated because agents copied patterns including flaws.
- Human review auto-approved everything — review discipline gap persists.

### Iteration 2 — Deep Retrospective (2026-03-20)

Deeper analysis of Phase 1 patterns. Full analysis discussed in session, key changes:

1. **Contract-driven specs.** Root cause of the regression was implicit behavioral contracts between tasks. Made contracts explicit in the task spec template with establishes/modifies/depends_on fields.

2. **Judge repositioned as code reviewer.** Phase 1 used the judge to re-test behaviors via curl — redundant with tests. Redefined: judge verifies design alignment, pattern compliance, and contract maintenance. Tests verify behavior. Different concerns.

3. **Gate 1b (full suite regression).** Formalized running the entire test suite after every task, not just task-specific tests. The Phase 1 regression was caught this way; now it's mandatory.

4. **Pattern templates.** Created canonical patterns (drf-crud, nested-endpoint, test-fixtures) to prevent dead code propagation. Agents reference patterns instead of copying from prior tasks.

5. **files.affected field.** Specs now list files from prior tasks that might need updating, not just files this task creates/modifies. Catches cross-task impact at spec time.

6. **Parallel execution planned.** Phase 1 was fully sequential. Phase 2 will try worktree isolation on independent tasks to test vtaskforge's core value proposition.

7. **Dogfooding planned.** Once CLI + bulk import exist, Phase 3 specs will be imported into vtaskforge and executed through the system itself.
