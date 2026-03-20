# Phase 2 — Execution Log

Tracks issues, observations, and metrics per task for the Phase 2 retrospective.

## Task 2.1 — Test factory infrastructure

- **Agent**: Sonnet
- **Gate 1b (Full suite)**: PASS — 568/568 tests, same count before and after
- **Gate 2 (Judge)**: Pending
- **Spec deviations**: None
- **Notes**:
  - 21 test files migrated to use factories
  - Largest single-task file modification scope so far
  - test_review_policy.py uses mocks — correctly left as-is
  - test_mixins.py and test_celery.py don't use domain models — left unchanged

## Task 2.2 — Claim expiry (Celery periodic task)

- **Agent**: Sonnet
- **Gate 1b (Full suite)**: PASS — 578/578
- **Spec deviations**: Added "claim_expired" to EVENT_TYPE_CHOICES in events/models.py — necessary, not in spec.
- **Notes**: Clean implementation. 10 tests with time mocking.

## Task 2.3 — Authentication (DRF TokenAuthentication)

- **Agent**: Sonnet
- **Gate 1b (Full suite)**: PASS — 586/586
- **Spec deviations**: None
- **Notes**:
  - api_client fixture now authenticated by default. Added unauthenticated_client for 401 tests.
  - Agent registration creates Django User + Token, returns token in response.
  - Concurrent claim tests updated to pass tokens through threads.
  - Test suite time jumped from ~4s to ~47s. Likely thread-based auth setup in claiming tests. Worth investigating if it grows further.

## Task 2.4 — Bulk import endpoint (parallel with 2.5)

- **Agent**: Sonnet
- **Gate 1b (Full suite)**: PASS — 608/608
- **Spec deviations**: Infers source_type and target_type from ref_type_map instead of hardcoding. Strictly more correct.
- **Notes**: 22 tests. Atomic transaction with rollback on validation errors. Ref resolution for cross-entity links works.

## Task 2.5 — CLI core project setup (parallel with 2.4)

- **Agent**: Sonnet
- **Gate 1a (CLI tests)**: PASS — 38/38 in 0.08s
- **Spec deviations**: Added pytest.ini with `-p no:django` to prevent interference from parent project.
- **Notes**: Clean Click setup. Config reads from ~/.vtf/config.yaml with env var override.
- **Process observation**: First successful parallel execution. 2.4 (Django) and 2.5 (CLI) had zero file overlap. Both completed independently.

## Tasks 2.6, 2.7, 2.8 — CLI commands (parallel, Step 4)

- **Agents**: 3x Sonnet in parallel
- **Gate 1a (CLI tests)**: PASS — 99/99 (18 workplan + 27 task + 16 agent + 38 core)
- **Gate 1b (Django tests)**: PASS — 608/608, no interference
- **Merge conflicts**: NONE — all three agents added their imports and cli.add_command() to cli.py without conflict
- **Spec deviations**: None
- **Notes**:
  - First triple parallel execution. Zero file conflicts despite all modifying cli.py.
  - Agent register command correctly creates unauthenticated client and saves returned token to config.
  - Process observation: parallel CLI command tasks are ideal candidates — each is an isolated command module with its own test file. The only shared file (cli.py) gets a single line added per command.
