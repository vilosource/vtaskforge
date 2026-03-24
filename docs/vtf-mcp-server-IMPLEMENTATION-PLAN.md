# vtf MCP Server Implementation Plan

Actionable task breakdown for implementing the MCP server defined in `vtf-mcp-server-SPECIFICATION.md`.

Follows the [VFF Development Manifesto](../../vilo-forge-factory/docs/development-MANIFESTO.md) principles, adapted for Python/Django.

## Phase Dependency Graph

```
P0 Service Layer ──> P1 MCP Skeleton ──> P2 Core Tools ──> P3 Management Tools ──> P4 Polish
     (refactor)        (infrastructure)    (executor)        (supervisor/judge)      (quality)
```

Each phase has a **quality gate** that must pass before the next phase begins.

## Development Manifesto Compliance

This plan follows the VFF Development Manifesto. Key rules adapted for Python/Django:

### Strict TDD (Manifesto 1.1)

Every task follows RED -> GREEN -> REFACTOR. No exceptions.

- **RED**: Write a failing test first. Import errors count as failures.
- **GREEN**: Write the minimum code to make it pass.
- **REFACTOR**: Clean up while keeping tests green.

Never write production code without a failing test that demands it.

### SOLID Principles (Manifesto 2)

- **Single Responsibility**: Each service class/function does one thing. `TaskService.claim()` claims. `EventService.record()` records. No "and".
- **Open/Closed**: New MCP tools extend the system without modifying existing services. Services are the stable core.
- **Interface Segregation**: Service functions have focused signatures. No god-services with 20 methods. Split by domain (TaskService, EventService, ReviewService).
- **Dependency Inversion**: MCP tools and REST views depend on service abstractions, not on each other. Neither layer imports the other.

### Interface First (Manifesto 7.1)

For each service:
1. Define the function signature and docstring (the contract)
2. Write tests against that contract
3. Implement the function to make tests pass

### One Commit Per Step (Manifesto 7.2)

Each task (P0.1, P0.2, ...) is one commit. If a commit description needs "and", split it.

### No Dead Code (Manifesto 7.3)

When extracting logic from views, delete the original inline code. Don't leave commented-out blocks or unused helpers.

---

## Testing and Verification Strategy

### Principles

1. **Existing tests are the safety net** — 801 tests cover the REST API. During P0 (service extraction), zero test changes means zero behavior changes. If an existing test breaks, we introduced a regression.

2. **New service functions get unit tests** — test the service layer in isolation, not through HTTP. These tests are fast, focused, and catch logic errors before integration. Use parametrized tests (Python equivalent of table-driven tests) for multiple cases.

3. **MCP tools get integration tests** — call the tool function directly with real Django DB (via `@pytest.mark.django_db`), verify the enriched response shape matches the spec. No HTTP involved.

4. **Contract tests enforce the spec** — response schemas from the SPECIFICATION are encoded as test assertions. If a response field is missing or the wrong type, the test fails.

5. **End-to-end smoke test** — after each MCP phase, manually verify Claude Code can connect and use the tools against the dev server.

### Test Pyramid for This Project

```
            /  E2E  \          Claude Code connects, claims a task, completes it
           /----------\
          / Integration \       MCP tool function → Django DB → enriched response
         /----------------\
        /   Service Unit    \   Service function → DB → result (no HTTP, no MCP)
       /----------------------\
      / Existing REST API (801) \  Don't touch — these are the regression safety net
     /----------------------------\
```

### Quality Gates

| Gate | Phase Transition | Criteria |
|------|-----------------|----------|
| G0 | P0 complete → start P1 | All 801 existing tests pass. New service unit tests pass. Views are thin wrappers calling services. No business logic in views. |
| G1 | P1 complete → start P2 | MCP server starts, Claude Code connects via stdio, `vtf_board_overview` returns correct data. Integration test passes. |
| G2 | P2 complete → start P3 | Full executor workflow test: next_work → claim_and_start → report_progress → submit_work. All enrichment fields present. |
| G3 | P3 complete → start P4 | All 9 tools have integration tests. search/detail/manage/review all work. Error responses are actionable. |
| G4 | P4 complete → ship | Error message quality audit done. README written. `.mcp.json` config works. Performance acceptable (<500ms per tool call). |

### Parametrized Tests (Table-Driven)

Following the manifesto's table-driven test requirement. Python equivalent uses `@pytest.mark.parametrize`:

```python
@pytest.mark.django_db
@pytest.mark.parametrize("status,expected_actions", [
    ("draft", ["submit", "cancel", "defer"]),
    ("todo", ["claim", "block", "cancel", "defer"]),
    ("doing", ["complete", "fail", "block", "cancel"]),
    ("blocked", ["unblock", "cancel", "defer"]),
    ("done", []),
    ("cancelled", []),
])
def test_get_available_actions(status, expected_actions):
    task = TaskFactory(status=status)
    actions = get_available_actions(task)
    assert set(actions) == set(expected_actions)
```

Use parametrized tests for:
- Status-dependent behavior (all 11 statuses)
- Error cases (multiple failure modes per service function)
- Response schema validation (multiple tools, same envelope structure)

### TDD Workflow Per Task

```
1. Write test             →  pytest -k "test_new_thing" → FAILS (RED)
2. Write minimum code     →  pytest -k "test_new_thing" → PASSES (GREEN)
3. Refactor               →  pytest -k "test_new_thing" → STILL PASSES
4. Full regression        →  pytest                     → ALL PASS (801+)
5. Commit
```

### How We Verify During Development

For each task:
1. **Before writing code**: run `docker compose exec api pytest` — establish baseline (all green)
2. **After writing code**: run same command — must still be all green
3. **For new code**: write tests first (TDD), then implement
4. **At phase boundary**: run full suite + manual smoke test + review quality gate checklist

---

## Phase 0: Service Layer Extraction

Pure refactor. No new features. No behavior changes. Existing tests must pass unchanged throughout.

### P0.1 — EventService

Extract event creation into a central service. This is the simplest extraction and unblocks all others.

**Create:** `src/events/services.py`

```python
from events.models import TaskEvent

def record_event(task, event_type: str, data: dict = None, triggered_by: str = ""):
    """Create a TaskEvent. Silent on failure (matches existing behavior)."""
    try:
        return TaskEvent.objects.create(
            task=task,
            event_type=event_type,
            data=data or {},
            triggered_by=triggered_by,
        )
    except Exception:
        pass
```

**Modify:** Replace all 5 inline `TaskEvent.objects.create()` calls:
- `src/tasks/views.py` lines 229, 325, 510
- `src/tasks/state_machine.py` line 91
- `src/tasks/celery_tasks.py` line 35

**Tests:** `tests/events/test_services.py`
- `test_record_event_creates_event` — verify TaskEvent row created
- `test_record_event_silent_on_error` — verify no exception raised on failure
- `test_record_event_returns_event` — verify return value

**Acceptance:** All 801 existing tests still pass. 5 callsites use `record_event()`.

**Depends on:** nothing

---

### P0.2 — TaskService: dependency resolution

Extract the duplicated dependency resolution logic shared by `claim()` and `claimable()`.

**Create:** `src/tasks/services.py`

```python
from links.models import Link
from tasks.models import Task

def resolve_dependencies(task_id: str) -> dict:
    """
    Check if all depends_on links for a task point to done tasks.
    Returns: {
        'resolved': bool,
        'dependencies': [{'id', 'title', 'status'}],
        'unresolved': [{'id', 'title', 'status'}]
    }
    """

def get_tasks_with_unresolved_deps(task_ids: list[str]) -> set[str]:
    """
    Given a list of task IDs, return the subset that have unresolved dependencies.
    Used by claimable() to filter efficiently.
    """
```

**Modify:**
- `src/tasks/views.py` `claim()` — replace lines 194-217 with `resolve_dependencies()` call
- `src/tasks/views.py` `claimable()` — replace lines 263-279 with `get_tasks_with_unresolved_deps()` call

**Tests:** `tests/tasks/test_services.py`
- `test_resolve_deps_no_deps_returns_resolved` — task with no links
- `test_resolve_deps_all_done_returns_resolved` — all targets are done
- `test_resolve_deps_some_not_done_returns_unresolved` — mixed statuses
- `test_resolve_deps_nonexistent_target_returns_unresolved` — dangling link
- `test_get_tasks_with_unresolved_deps_filters_correctly` — batch check

**Acceptance:** All 801 existing tests pass (especially `test_claiming.py`). Dependency logic lives in one place.

**Depends on:** nothing

---

### P0.3 — TaskService: claim logic

Extract the atomic claim from `TaskViewSet.claim()` into a service function.

**Add to:** `src/tasks/services.py`

```python
from django.db import transaction

class ClaimError(Exception):
    """Raised when a claim cannot be completed."""
    def __init__(self, message: str, code: str, status_code: int = 422):
        self.message = message
        self.code = code  # e.g., "tag_mismatch", "already_claimed", "deps_unmet"
        self.status_code = status_code
        super().__init__(message)

def claim_task(task_id: str, agent_id: str, agent_tags: list[str] = None) -> Task:
    """
    Atomically claim a task for an agent.

    Validates: status is todo, tags match, assignment allowed, deps resolved.
    Sets: claimed_by, claimed_at, claim_expires_at. Transitions to doing.

    Raises ClaimError with descriptive message on failure.
    Returns the claimed Task instance.
    """
```

**Modify:**
- `src/tasks/views.py` `claim()` — reduce to ~15 lines: parse request, call `claim_task()`, catch `ClaimError`, return response

**Tests:** `tests/tasks/test_services.py`
- `test_claim_task_success` — basic claim
- `test_claim_task_sets_claim_fields` — claimed_by, claimed_at, claim_expires_at
- `test_claim_task_tag_mismatch_raises` — task.requires not subset of agent tags
- `test_claim_task_wrong_status_raises` — task not in todo
- `test_claim_task_assigned_to_other_raises` — 403 case
- `test_claim_task_unresolved_deps_raises` — deps not done
- `test_claim_task_creates_event` — claimed event recorded
- `test_claim_task_atomic` — concurrent claims, one wins

**Acceptance:** All 801 existing tests pass. `test_claiming.py` (the comprehensive claim test file) passes without modification. View method is now ~15 lines.

**Depends on:** P0.1 (EventService), P0.2 (dependency resolution)

---

### P0.4 — TaskService: find claimable

Extract the claimable query logic.

**Add to:** `src/tasks/services.py`

```python
def find_claimable_tasks(
    project_id: str = None,
    tags: list[str] = None,
    agent_id: str = None,
) -> list[Task]:
    """
    Find tasks in 'todo' status that:
    - Have all dependencies resolved
    - Match the given tags (task.requires is subset of tags)
    - Are unassigned or assigned to agent_id
    """
```

**Modify:**
- `src/tasks/views.py` `claimable()` — reduce to request parsing + call service + format response

**Tests:** `tests/tasks/test_services.py`
- `test_find_claimable_basic` — returns todo tasks
- `test_find_claimable_excludes_tasks_with_unmet_deps`
- `test_find_claimable_filters_by_tags`
- `test_find_claimable_filters_by_assignment`
- `test_find_claimable_filters_by_project`

**Acceptance:** All 801 existing tests pass. Claimable endpoint tests pass without modification.

**Depends on:** P0.2 (dependency resolution)

---

### P0.5 — ReviewService

Extract review routing logic from `ReviewViewSet.create()`.

**Create:** `src/reviews/services.py`

```python
class ReviewError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

def submit_review(
    task_id: str,
    decision: str,  # "approved", "changes_requested", "rejected"
    reason: str = "",
    reviewer_id: str = "",
    reviewer_type: str = "human",
) -> dict:
    """
    Submit a review decision for a task in review status.
    Handles state transition routing based on decision and current status.
    Returns: {'review': Review, 'task': Task, 'previous_status': str}
    Raises ReviewError if task not in review status.
    """
```

**Modify:**
- `src/reviews/views.py` `create()` — reduce to parse request, call service, return response

**Tests:** `tests/reviews/test_services.py`
- `test_submit_review_approved_start_review` — pending_start_review → todo
- `test_submit_review_approved_completion_review` — pending_completion_review → done
- `test_submit_review_changes_requested` — sets review_return_to, transitions
- `test_submit_review_not_in_review_status_raises`
- `test_submit_review_creates_review_record`

**Acceptance:** All 801 existing tests pass. `tests/reviews/test_api.py` passes unchanged.

**Depends on:** P0.1 (EventService)

---

### P0.6 — Fix celery expire_stale_claims

Make the celery task use the state machine instead of direct status mutation.

**Modify:** `src/tasks/celery_tasks.py`
- Replace direct `task.status = "needs_attention"` with `perform_transition(task, "needs_attention", triggered_by="system")`
- Replace inline event creation with `record_event()`
- Keep claim field clearing (claimed_by, claimed_at, claim_expires_at)

**Tests:** `tests/tasks/test_claim_expiry.py` — existing tests should still pass. Add:
- `test_expire_creates_event_via_service` — verify event created through EventService
- `test_expire_uses_state_machine` — verify transition goes through perform_transition

**Acceptance:** All 801 existing tests pass. Celery task uses state machine consistently.

**Depends on:** P0.1 (EventService)

---

### P0.7 — TaskService: enrichment helpers

Add helper functions that MCP tools will need. These compose existing data into the enriched response format.

**Add to:** `src/tasks/services.py`

```python
def get_task_context(task_id: str) -> dict:
    """
    Full task context for MCP responses: task fields, spec, deps,
    reviews, recent events, notes, available actions.
    """

def get_available_actions(task) -> list[str]:
    """
    Given a task's current status, return the list of valid MCP actions.
    Maps VALID_TRANSITIONS to tool names.
    """

def get_board_summary(project_id: str, workplan_id: str = None) -> dict:
    """
    Aggregate board state: counts by status, attention items,
    pending reviews, active agents.
    """
```

**Tests:** `tests/tasks/test_services.py`
- `test_get_task_context_includes_all_fields`
- `test_get_available_actions_for_each_status` — parametrized across all 11 statuses
- `test_get_board_summary_counts`
- `test_get_board_summary_attention_items`
- `test_get_board_summary_pending_reviews`

**Acceptance:** All helpers return correct data. These are new functions, no regression risk.

**Depends on:** P0.2 (dependency resolution)

---

### Quality Gate G0

**Regression:**
- [ ] `docker compose exec api pytest` — all 801+ tests pass unchanged

**SOLID compliance:**
- [ ] Single Responsibility: each service function does one thing, describable in one sentence
- [ ] Dependency Inversion: views import services, never the reverse. MCP layer does not exist yet.
- [ ] No dead code: inline logic deleted from views after extraction

**Completeness:**
- [ ] `services.py` exists in tasks/, events/, reviews/
- [ ] No business logic remains in view methods (views are <20 lines each)
- [ ] All 5 event creation sites use `record_event()`
- [ ] Celery task uses state machine
- [ ] New service unit tests all pass (parametrized where applicable)
- [ ] `git log` shows one commit per task (P0.1 through P0.7)

---

## Phase 1: MCP Server Skeleton

### P1.1 — Add MCP SDK dependency

**Modify:** `requirements/base.txt` — add `mcp` package

**Verify:** `docker compose build api` succeeds, `docker compose exec api python -c "import mcp"` works

**Depends on:** P0 complete (G0 passed)

---

### P1.2 — MCP server entry point

**Create:** `src/mcp_server/__init__.py`, `src/mcp_server/server.py`

```python
# server.py — MCP server with Django ORM access
import django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "vtaskforge.settings.dev")
django.setup()

from mcp.server import Server

server = Server("vtf")

# Tool registration happens here
# Auth middleware reads VTF_TOKEN from env
```

**Create:** `src/mcp_server/auth.py` — token validation against Django authtoken

**Create:** `src/mcp_server/responses.py` — shared response formatting (success/error envelope, available_actions)

**Tests:** `tests/mcp_server/test_server.py`
- `test_server_starts` — server instance creates without error
- `test_response_envelope_success` — success format matches spec
- `test_response_envelope_error` — error format matches spec

**Depends on:** P1.1

---

### P1.3 — vtf_board_overview tool (proof of concept)

**Create:** `src/mcp_server/tools/board.py`

Wire up the first tool using `get_board_summary()` from P0.7.

**Tests:** `tests/mcp_server/test_board_tool.py`
- `test_board_overview_returns_counts` — verify status counts
- `test_board_overview_includes_attention_items` — blocked/needs_attention tasks listed
- `test_board_overview_includes_pending_reviews`
- `test_board_overview_includes_available_actions`
- `test_board_overview_with_project_filter`
- `test_board_overview_empty_project` — no tasks, clean response

**Manual verification:** Configure `.mcp.json`, connect Claude Code, call `vtf_board_overview`.

**Depends on:** P1.2, P0.7

---

### Quality Gate G1

**Regression:**
- [ ] All existing + new tests pass

**SOLID compliance:**
- [ ] MCP server code lives in `src/mcp_server/` — isolated from Django apps
- [ ] MCP tools call services, never models or views directly
- [ ] Response formatting is a single shared function (DRY)

**Completeness:**
- [ ] MCP server starts via `python -m mcp_server.server`
- [ ] Claude Code connects via stdio transport
- [ ] `vtf_board_overview` returns correct data from dev database
- [ ] Response matches spec format (success, data, available_actions, message)

---

## Phase 2: Core Agent Workflow Tools

The tools an executor agent needs for the claim-work-submit cycle.

### P2.1 — vtf_next_work

**Create:** `src/mcp_server/tools/workflow.py`

Uses `find_claimable_tasks()` from P0.4, enriched with dep status and spec summary.

**Tests:** `tests/mcp_server/test_workflow_tools.py`
- `test_next_work_returns_best_candidate`
- `test_next_work_matches_agent_tags`
- `test_next_work_resolves_dependencies`
- `test_next_work_includes_spec_summary`
- `test_next_work_includes_alternatives_count`
- `test_next_work_no_work_available` — returns null data with helpful message
- `test_next_work_with_project_filter`

**Depends on:** P1.3 (server infrastructure proven)

---

### P2.2 — vtf_claim_and_start

Uses `claim_task()` from P0.3 + `get_task_context()` from P0.7.

**Tests:**
- `test_claim_and_start_success` — claims and returns full context
- `test_claim_and_start_includes_spec`
- `test_claim_and_start_includes_deps`
- `test_claim_and_start_includes_test_command`
- `test_claim_and_start_includes_available_actions`
- `test_claim_and_start_tag_mismatch_error` — actionable error message
- `test_claim_and_start_deps_unmet_error` — includes which dep is blocking

**Depends on:** P2.1 (can test the full next_work → claim flow)

---

### P2.3 — vtf_report_progress

Composes heartbeat extension + note creation.

**Tests:**
- `test_report_progress_extends_claim`
- `test_report_progress_adds_note`
- `test_report_progress_without_note` — heartbeat only
- `test_report_progress_not_doing_error`

**Depends on:** P2.2

---

### P2.4 — vtf_submit_work

Uses `perform_transition()` + `get_effective_review_flags()` + note creation.

**Tests:**
- `test_submit_work_completes_task`
- `test_submit_work_triggers_review_when_configured`
- `test_submit_work_adds_completion_note`
- `test_submit_work_includes_milestone_progress`
- `test_submit_work_not_doing_error`

**Depends on:** P2.2

---

### P2.5 — Executor workflow end-to-end test

A single test that exercises the complete cycle: `next_work → claim_and_start → report_progress → submit_work`.

**Create:** `tests/mcp_server/test_executor_workflow.py`

```python
@pytest.mark.django_db
def test_full_executor_workflow():
    """End-to-end: find work, claim it, report progress, submit."""
    # Setup: project, workplan, milestone, todo task with spec
    # Step 1: vtf_next_work returns the task
    # Step 2: vtf_claim_and_start claims it, returns full context
    # Step 3: vtf_report_progress extends claim + adds note
    # Step 4: vtf_submit_work completes the task
    # Verify: task is done (or pending_completion_review), events recorded
```

**Depends on:** P2.1-P2.4

---

### Quality Gate G2

**Checklist:**
- [ ] All existing + new tests pass
- [ ] Full executor workflow test passes
- [ ] All enrichment fields present in responses (available_actions, deps, spec, test_command)
- [ ] Error messages are actionable (include what to do next)
- [ ] Manual smoke test: Claude Code runs the full claim-work-submit cycle

---

## Phase 3: Management and Review Tools

### P3.1 — vtf_search_tasks

Uses Django ORM queries with enriched results.

**Tests:**
- `test_search_by_status`
- `test_search_by_project`
- `test_search_by_milestone`
- `test_search_by_labels`
- `test_search_text_query`
- `test_search_pagination`
- `test_search_includes_available_actions_per_task`

**Depends on:** P2 complete (G2 passed)

---

### P3.2 — vtf_task_detail

Uses `get_task_context()` from P0.7.

**Tests:**
- `test_task_detail_includes_all_sections` — spec, deps, reviews, events, notes
- `test_task_detail_shows_available_transitions`
- `test_task_detail_not_found_error`

**Depends on:** P3.1

---

### P3.3 — vtf_manage_task

Unified create/update/transition tool.

**Tests per action:**
- `test_manage_create_task`
- `test_manage_update_title`
- `test_manage_update_labels`
- `test_manage_submit_task`
- `test_manage_block_task`
- `test_manage_unblock_task`
- `test_manage_defer_task`
- `test_manage_cancel_task`
- `test_manage_delete_task`
- `test_manage_assign_task`
- `test_manage_reset_task`
- `test_manage_invalid_transition_error` — actionable error with valid transitions listed

**Depends on:** P3.2

---

### P3.4 — vtf_review_task

Uses `submit_review()` from P0.5.

**Tests:**
- `test_review_approve_start` — pending_start_review → todo
- `test_review_approve_completion` — pending_completion_review → done
- `test_review_changes_requested` — with reason
- `test_review_not_in_review_status_error`
- `test_review_includes_milestone_progress`

**Depends on:** P3.3

---

### P3.5 — Supervisor workflow end-to-end test

**Create:** `tests/mcp_server/test_supervisor_workflow.py`

```python
@pytest.mark.django_db
def test_supervisor_board_to_review_workflow():
    """Supervisor checks board, finds pending review, approves it."""
    # Setup: project with tasks in various states, one pending_completion_review
    # Step 1: vtf_board_overview — sees pending review
    # Step 2: vtf_task_detail — reviews the task details
    # Step 3: vtf_review_task — approves it
    # Verify: task is done, milestone progress updated
```

**Depends on:** P3.1-P3.4

---

### Quality Gate G3

**Checklist:**
- [ ] All existing + new tests pass
- [ ] All 9 tools have integration tests
- [ ] Both workflow e2e tests pass (executor + supervisor)
- [ ] Error responses include valid transitions and actionable guidance
- [ ] Response schemas match the SPECIFICATION for all tools

---

## Phase 4: Polish

### P4.1 — Error message quality audit

Review every error path across all 9 tools. Each error must:
- Explain what went wrong
- Explain why (current state)
- Suggest what to do instead (available_actions)

No raw exceptions or generic messages.

**Deliverable:** Error message test for each tool's error paths.

---

### P4.2 — Claude Code configuration

**Create:** `.mcp.json` at project root

```json
{
  "mcpServers": {
    "vtf": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/vtaskforge/src",
      "env": {
        "VTF_TOKEN": "...",
        "DJANGO_SETTINGS_MODULE": "vtaskforge.settings.dev"
      }
    }
  }
}
```

**Deliverable:** Working config that Claude Code picks up automatically.

---

### P4.3 — Performance verification

**Test:** Each tool completes in <500ms with a database of 100+ tasks.

**Create:** `tests/mcp_server/test_performance.py`
- Seed 100 tasks across multiple milestones
- Time each tool call
- Assert <500ms

---

### P4.4 — Documentation

**Create:** `docs/mcp-server-README.md`
- Setup instructions
- Tool reference (generated from tool descriptions)
- Configuration guide
- Troubleshooting

---

### Quality Gate G4

**Checklist:**
- [ ] All tests pass (existing + new, target: 900+)
- [ ] All error messages audited and actionable
- [ ] `.mcp.json` works with Claude Code
- [ ] All tools respond in <500ms
- [ ] README covers setup and usage
- [ ] Manual e2e: Claude Code completes a full task lifecycle via MCP

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Service extraction breaks existing API behavior | High | Medium | Run full 801-test suite after every change. Zero tolerance for test modifications in P0. |
| MCP SDK API changes | Medium | Low | Pin SDK version. Isolate MCP code in `src/mcp_server/`. |
| Django ORM in MCP process lacks proper setup | High | Medium | P1.2 validates Django setup works. Follow django.setup() pattern from manage.py. |
| Tool response schemas drift from spec | Medium | Medium | Contract tests assert response shape. Spec is source of truth. |
| Performance issues with enriched responses | Medium | Low | P0.7 enrichment helpers use select_related/prefetch. P4.3 catches regressions. |
| Concurrent MCP + REST access causes conflicts | Low | Low | Both use same Django ORM with same transaction isolation. No new concurrency concerns. |

## Commit Strategy

One commit per task (P0.1, P0.2, etc.). Each commit message references the task ID:

```
Extract EventService from inline TaskEvent creation (P0.1)
Extract dependency resolution to TaskService (P0.2)
Extract claim logic to TaskService (P0.3)
...
```

This makes it easy to bisect if a regression appears.
