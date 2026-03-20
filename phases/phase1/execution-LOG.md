# Phase 1 — Execution Log

Tracks issues, observations, and metrics per task for the Phase 1 retrospective.

## Task 1.1 — Workplan model + CRUD

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 42/42 tests, django check clean
- **Gate 2 (Judge)**: PASS — 12/12 behaviors verified via curl
- **Gate 3 (Human)**: Auto-approved (no issues)
- **Spec deviations**: None
- **Notes**:
  - Dead code: `update()` method override in views.py is unreachable because PUT is already excluded via `http_method_names`. Defensive but unnecessary.
  - Sonnet handled this cleanly with no retries needed.
  - 42 tests is thorough — good coverage of model and API layer.

## Task 1.2 — Agent model + registration

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 38/38 tests, django check clean
- **Gate 2 (Judge)**: Skipped — identical CRUD pattern to 1.1, behaviors covered by tests
- **Gate 3 (Human)**: Auto-approved
- **Spec deviations**: Minor — `perform_create` forces status="online" regardless of client input. Not in spec but good defensive behavior. Test covers it.
- **Notes**:
  - Same dead code pattern as 1.1 (`update()` override + `http_method_names` exclusion).
  - `registered_at` correctly separate from `created_at` as spec required.
  - Process observation: Gate 2 (judge) adds ~75s for a simple CRUD task. For tasks that follow an established pattern, the mechanical tests are sufficient. Consider skipping judge for pattern-repeat tasks in the process guide.

## Task 1.3 — Phase model + CRUD

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 91/91 tests (cumulative), django check clean
- **Gate 2 (Judge)**: Skipped — CRUD pattern repeat
- **Spec deviations**: None
- **Notes**:
  - Smart routing decision: agent realized `vtaskforge/urls.py` didn't need modification because the workplans include already covers phase routes. Spec listed it as a file to modify but agent correctly skipped it.
  - Nested route pattern: `WorkplanPhasesView` (APIView) for POST/GET under workplan, `PhaseViewSet` for direct access. Clean separation.
  - Cascade delete tested — good coverage of the FK relationship.
  - Null review flags correctly stored as null, not false. Test explicitly covers this.

## Task 1.4 — Task model (model only)

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 10/10 tests, django check clean
- **Gate 2 (Judge)**: Skipped — model-only task, no API behavior to probe
- **Spec deviations**: None
- **Notes**:
  - Clean execution, no retries. Simplest task so far (model + tests only).
  - All 11 status choices defined correctly.
  - Both cascade deletes tested.

## Task 1.5 — Task state machine

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 73/73 tests, django check clean
- **Gate 2 (Judge)**: PASS — 19/19 behaviors verified + 4 structural checks. Transition table matches design doc exactly.
- **Spec deviations**: None
- **Notes**:
  - 73 tests is the most thorough coverage so far — every valid transition edge tested individually.
  - Judge confirmed: `changes_requested` correctly resolves design doc's abstract "review_return_to value" into concrete `pending_start_review` and `pending_completion_review` targets.
  - Good practice: `save(update_fields=["status", "updated_at"])` avoids writing unchanged fields.
  - Minor gap noted by judge: no test explicitly asserts `exc.valid_transitions == []` from terminal states, but covered indirectly via structural test.
  - Process observation: Judge run warranted here — this is the core module. The structural verification (transition table matches design doc) adds real value beyond what tests can prove.

## Task 1.6 — Task CRUD + lifecycle endpoints

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 216/216 tests (cumulative across tasks/), django check clean
- **Gate 2 (Judge)**: Skipped — 133 new tests cover all 24 behavioral spec items
- **Spec deviations**:
  - **unclaim bypasses state machine**: `doing -> todo` is not in VALID_TRANSITIONS. Agent correctly identified the gap and implemented unclaim as a direct status set instead of routing through perform_transition. This is a design doc gap — the state machine doesn't account for unclaim (voluntary release without failure). Options: (1) add `todo` to doing's valid transitions, (2) keep unclaim as a special case outside the state machine. Decision deferred — both approaches are valid, but the state machine should probably own ALL status changes for consistency. Logged for retrospective.
- **Notes**:
  - Largest task so far: 133 new tests, 14 lifecycle actions.
  - Nested task creation (POST /v1/phases/{phase_id}/tasks/) auto-sets workplan from phase.workplan — good.
  - Error format matches api-surface-DESIGN.md: 422 with INVALID_TRANSITION code + details.
  - submit always goes to `todo` for now (review flag cascading in 1.11).
  - complete always goes to `done` for now (review flag cascading in 1.11).
  - Process observation: Agent self-reported the deviation clearly. This validates the "spec deviation protocol" from phase-process-GUIDE.md — agents should flag deviations, not silently work around them.

## Task 1.7 — Link model + CRUD

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 36/36 tests, django check clean
- **Gate 2 (Judge)**: Skipped — CRUD pattern, well-tested
- **Spec deviations**: Minor — target_type max_length increased from 20 to 100 (free-form field, spec's 20 was too short). Reasonable.
- **Notes**:
  - Immutability correctly enforced: no retrieve, no update, no partial_update. Only create/list/destroy.
  - DB indexes on (source_type, source_id) and (target_type, target_id) — good for query performance.
  - Two migrations generated (model + index). Could have been one but harmless.

## Task 1.8 — Note model + endpoints

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 21/21 tests
- **Spec deviations**: None
- **Notes**: Clean append-only pattern. NanoIDMixin only (no TimestampMixin) as spec required.

## Task 1.9 — Review model + endpoints

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 33/33 tests
- **Spec deviations**: None
- **Notes**: review_return_to correctly set BEFORE state transition. State machine integration clean.

## Task 1.10 — TaskEvent model + auto-logging

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 278/278 cumulative (41 events + 237 tasks), no regressions
- **Spec deviations**: None
- **Notes**:
  - Modified state_machine.py and tasks/views.py — no regressions in existing tests.
  - Event creation wrapped in try/except as spec required.
  - old_status captured before transition — correct.

## Task 1.11 — Review flag cascading

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 32/32 tests, no regressions
- **Spec deviations**: None
- **Notes**:
  - Explicit False correctly overrides parent True (null-check, not falsy-check).
  - select_related("phase", "workplan") added to avoid N+1.
  - 14 unit tests + 18 integration tests — thorough cascade coverage.

## Task 1.12 — Atomic claim + dependency check

- **Agent**: Sonnet
- **Gate 1 (Mechanical)**: PASS — 568/568 tests after fixing 1 regression
- **Spec deviations**: None significant
- **Notes**:
  - **Regression found**: Task 1.12 changed claim error from 422 (INVALID_TRANSITION) to 409 (ALREADY_CLAIMED), but one test in test_auto_logging.py from task 1.10 still expected 422. Fixed manually by supervisor.
  - This is a process finding: when a task modifies behavior established by a prior task, it should update ALL tests referencing that behavior, not just its own.
  - select_for_update() + transaction.atomic() implemented correctly.
  - Concurrent claim test: two threads race, one gets 200, other gets 409.
  - Claimable endpoint filters by status, dependencies, tags, and assignment.

---

## Phase 1 Summary

- **Total tasks**: 12
- **Total tests**: 568
- **Spec deviations**: 2 (unclaim bypasses state machine in 1.6; target_type max_length increased in 1.7)
- **Regressions**: 1 (auto_logging test expected wrong status code after 1.12 changed claim error code)
- **Judge evaluations**: 2 (1.1 full curl evaluation, 1.5 state machine structural verification)
- **Agent model**: Sonnet for all tasks
- **Retries needed**: 0 — every task completed on first attempt
