# vtaskforge — Milestone Execution Process Guide

Status: Active (2026-03-20)
Iteration: 2 (post-Milestone 1 deep retrospective)

This guide defines how milestones are planned, executed, and verified. It is a living document — each milestone execution produces findings that improve the process for the next milestone.

## Roles

| Role | Who | Responsibility |
|---|---|---|
| Supervisor | Human or orchestrating agent | Writes task specs, dispatches agents, final review authority |
| Executor | Sonnet subagent | Implements task per spec, reports completion and deviations |
| Judge | Opus agent | Code review against design docs, pattern compliance, contract verification |

## Task Spec Template

Every task in a milestone follows this structure:

```yaml
id: <milestone>.<sequence>
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
1. Supervisor writes task spec
2. Supervisor dispatches Sonnet subagent with task spec
3. Sonnet executes, commits
4. Gate 1a — Task-specific tests:
   - Run test_command (pytest/vitest for this task's tests)
   - If fail → back to Sonnet with failure details
5. Gate 1b — Full suite regression:
   - Run all test suites (Django + CLI + web)
   - If fail → agent must fix regressions
6. Gate 1c — Deployment smoke test (if task touches deployment boundary):
   - Rebuild dogfood image
   - Run deployment-smoke.spec.ts against built artifact
   - Catches: asset serving, auth flow, MIME types, SSE, routing
   - If fail → agent must fix deployment issues
7. Gate 2 — Judge code review (if judge: true):
   - Opus judge reads code + design docs
   - Verifies: design alignment, pattern compliance, blast radius
   - Produces structured verdict
8. Approve → move to next task
```

### Gate Details

**Gate 1a (Task tests)** — fast feedback. Runs only the task's test_command. Catches implementation bugs immediately.

**Gate 1b (Full suite)** — regression detection. Runs the entire test suite. Catches cross-task breakage. Mandatory on every task.

**Gate 1c (Deployment smoke test)** — environment boundary verification. Runs the built Docker artifact through a real browser via Playwright. This gate catches bugs that are **invisible to unit and integration tests** because they only manifest when the application runs in its production-like environment.

Gate 1c is triggered when a task modifies any **deployment boundary file**:
- `Dockerfile*`, `docker-compose*` — container build/runtime
- `settings/base.py`, `settings/prod.py` — shared or production configuration
- `urls.py` — routing (affects what Django serves vs what the SPA catches)
- `requirements/*.txt` — dependency changes
- `web/vite.config.ts` — frontend build configuration
- Middleware, auth classes, static file configuration

Gate 1c runs: `cd web && npx playwright test tests/deployment-smoke.spec.ts`

The deployment smoke test verifies:
1. Login page renders for unauthenticated users (no blank 401 page)
2. Login with credentials works and reaches the workplan list
3. SPA assets serve with correct MIME types (no catch-all interception)
4. API responds through Django (not just Vite proxy)
5. Kanban board loads without console errors
6. SSE endpoint accepts browser connections (no 406 from content negotiation)

**Why this gate exists:** Milestone 4 shipped three production bugs that all tests passed on:
- SPA asset MIME types (Vite serves correctly, Django's catch-all returned HTML)
- Missing login page (dev uses localStorage token, real users have no way in)
- SSE 406 (DRF content negotiation rejects text/event-stream from EventSource)

All three were invisible to Gate 1a and Gate 1b because those tests run in a different environment than production. Gate 1c is the only gate that tests the actual deployed artifact.

**Gate 2 (Judge code review)** — design alignment. The judge is a code reviewer, NOT a behavior tester. Tests verify behavior. The judge verifies:
- Does the implementation match the design doc's intent?
- Does the code follow the established pattern (or introduce dead code)?
- Are there N+1 queries, missing indexes, or architectural issues?
- Blast radius: were all consumers of changed interfaces updated?

The judge does NOT:
- Re-test behaviors via curl or browser (tests and Gate 1c do that)
- Make design decisions or suggest improvements
- Block on code style preferences

## Testing Strategy by Project Type

Different parts of the system require different testing approaches. The gate structure (1a → 1b → judge) stays the same, but the tools change.

### Backend (Django/DRF)

| Layer | Tool | What it tests | When to run |
|---|---|---|---|
| Unit | pytest + pytest-django | Models, state machine, business logic | Gate 1a |
| Integration | pytest + DRF test client | API endpoints, auth, serialization | Gate 1a |
| E2E | vtf-blackbox-tester (curl) | Full lifecycle across endpoints | After milestone completion |

```yaml
# Task spec for backend tasks
test_command: "docker compose exec api pytest tests/tasks/test_claiming.py"
```

Gate 1b (full suite): `docker compose exec api pytest tests/ && pytest cli/tests/`

### Frontend (React/Web UI)

| Layer | Tool | What it tests | When to run |
|---|---|---|---|
| Unit | Vitest + React Testing Library | Components in isolation, hooks, utilities | Gate 1a |
| Integration | Vitest + MSW (Mock Service Worker) | Components with mocked API responses | Gate 1a |
| E2E | Playwright | Real browser, real clicks, real page loads | Gate 1a + after milestone |

```yaml
# Task spec for frontend tasks
test_command:
  unit: "cd web && npx vitest run"
  e2e: "cd web && npx playwright test tests/kanban.spec.ts"
```

Gate 1b (full suite): `docker compose exec api pytest tests/ && pytest cli/tests/ && cd web && npx vitest run && npx playwright test`

### Playwright as the Web Black-Box Tester

Playwright is the curl equivalent for web UIs. It opens a real browser and tests the application as a user would:

```typescript
test('task moves to doing column after claim', async ({ page }) => {
  await page.goto('/workplans/abc123');
  const taskCard = page.locator('text=Fix unclaim');
  await expect(taskCard).toBeVisible();

  await taskCard.click();
  await page.locator('button:text("Claim")').click();

  // Verify task moved to doing column
  const doingColumn = page.locator('[data-column="doing"]');
  await expect(doingColumn.locator('text=Fix unclaim')).toBeVisible();
});
```

Playwright tests verify:
- Pages render correctly
- Navigation works
- User interactions trigger correct API calls
- SSE updates appear without page refresh
- Error states display properly

### SSE Testing

SSE live updates require special testing:
- **Unit**: Mock EventSource, verify component reacts to events
- **Integration**: Vitest with a fake SSE server
- **E2E**: Playwright creates data via API, verifies the UI updates within a timeout

```typescript
test('SSE updates kanban board live', async ({ page, request }) => {
  await page.goto('/workplans/abc123');

  // Create a task via API (bypassing the UI)
  await request.post('/v1/milestones/def456/tasks/', {
    data: { title: 'New task from API' },
    headers: { Authorization: 'Token ...' },
  });

  // Verify the task appears on the board without refresh
  await expect(page.locator('text=New task from API')).toBeVisible({ timeout: 5000 });
});
```

### Judge Considerations for Web Tasks

The judge reviews frontend code for:
- **Component structure**: Clean separation of concerns, no business logic in components
- **API integration**: Uses the shared API client, handles loading/error states
- **Accessibility**: Semantic HTML, ARIA attributes, keyboard navigation
- **Blast radius**: API response format changes reflected in mocks (MSW handlers)
- **Performance**: No unnecessary re-renders, proper memoization for large lists

The judge does NOT:
- Evaluate visual design or CSS aesthetics
- Test in a browser (Playwright does that)
- Judge framework-specific style preferences (class vs functional components)

### Cross-Stack Blast Radius

Web projects introduce a new blast radius surface: **the API contract between backend and frontend.**

When a backend task changes an API response format:
1. The executor must search frontend code for consumers (API client calls, TypeScript types, MSW mock handlers)
2. The executor must update all frontend consumers and mocks
3. The judge must verify no stale mocks remain in MSW handlers

This is the same blast radius principle, but the consumer is in a different language/framework. The search pattern: grep for the endpoint path in the web/ directory.

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
- Fixture: milestone — creates a Milestone under workplan
- Fixture: task — creates a Task under milestone (status=draft)
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

## Milestone Retrospective

After each milestone completes, document:

1. **What worked** — process elements that should be kept
2. **What didn't work** — failures, friction, wasted time
3. **Spec quality** — were specs detailed enough? Too detailed?
4. **Gate effectiveness** — did each gate catch real issues? False positives?
5. **Model performance** — did Sonnet handle the tasks? Which needed escalation?
6. **Process changes** — concrete changes to this guide for the next milestone

Append retrospective findings to this document as versioned iterations.

## Improvement Roadmap

Improvements are milestone-based when they can be applied:

### Do now (before next milestone specs)
- [x] Contract-driven specs (added to template)
- [x] Gate 1b full suite regression (added to execution flow)
- [x] Redefine judge as code reviewer (updated gate details)
- [x] Pattern templates (added DRF patterns)

### Do during Milestone 2 (learn by doing)
- [ ] Test factory infrastructure (make it an early task, all subsequent tasks use it)
- [ ] Try parallel execution with worktree isolation on independent tasks
- [ ] Validate pattern templates work in practice

### Do when ready (Milestone 3+)
- [ ] Design review gate before execution (formalize once enough pattern exists)
- [ ] Dogfooding — import Milestone 3 specs into vtaskforge, execute through the system itself
- [ ] Extract contracts into shared contracts/ directory

---

## Iteration Log

### Iteration 0 — Pre-Milestone 1 (2026-03-20)

Based on Milestone 0 dry run findings (see `milestones/milestone0/findings-ANALYSIS.md`):

- **Issue #1 (Port exposure):** Specs must trace dependency chains. Added constraints field to task template.
- **Issue #2 (No git isolation):** Added Git Isolation Rules section with worktree vs sequential guidance.
- **Issue #3 (Spec errors):** Added Spec Deviation Protocol. Agents must flag deviations, not silently fix.
- **Issue #4 (Agent capability):** Defaulted to Sonnet executors with calibrated spec detail. Opus reserved for judge and escalation.
- **Issue #5 (Pyright):** No process change needed. Dev tooling concern.
- **Issue #6 (Review discipline):** Added three-gate verification flow (mechanical → judge → human). Review is structured, not ad-hoc.

### Iteration 1 — Post-Milestone 1 (2026-03-20)

Milestone 1 executed 12 tasks sequentially with Sonnet executors. 568 tests, 0 retries, 2 minor spec deviations, 1 cross-task regression. Full findings in `milestones/milestone1/execution-LOG.md`.

Key findings:
- Sonnet handled everything. Zero escalations.
- Cross-task regression: task 1.12 changed claim error code (422→409), broke test from task 1.10.
- Judge wasteful on CRUD pattern-repeat tasks, valuable on core logic (state machine).
- Dead code propagated because agents copied patterns including flaws.
- Human review auto-approved everything — review discipline gap persists.

### Iteration 2 — Deep Retrospective (2026-03-20)

Deeper analysis of Milestone 1 patterns. Full analysis discussed in session, key changes:

1. **Contract-driven specs.** Root cause of the regression was implicit behavioral contracts between tasks. Made contracts explicit in the task spec template with establishes/modifies/depends_on fields.

2. **Judge repositioned as code reviewer.** Milestone 1 used the judge to re-test behaviors via curl — redundant with tests. Redefined: judge verifies design alignment, pattern compliance, and contract maintenance. Tests verify behavior. Different concerns.

3. **Gate 1b (full suite regression).** Formalized running the entire test suite after every task, not just task-specific tests. The Milestone 1 regression was caught this way; now it's mandatory.

4. **Pattern templates.** Created canonical patterns (drf-crud, nested-endpoint, test-fixtures) to prevent dead code propagation. Agents reference patterns instead of copying from prior tasks.

5. **files.affected field.** Specs now list files from prior tasks that might need updating, not just files this task creates/modifies. Catches cross-task impact at spec time.

6. **Parallel execution planned.** Milestone 1 was fully sequential. Milestone 2 will try worktree isolation on independent tasks to test vtaskforge's core value proposition.

7. **Dogfooding planned.** Once CLI + bulk import exist, Milestone 3 specs will be imported into vtaskforge and executed through the system itself.

### Iteration 3 — Post-Milestone 3 (2026-03-20)

Milestone 3 executed 6/7 tasks with standardized executor prompts (no hand-crafted glue). All passed first attempt. Dogfooding via vtf-dogfood release stack validated.

Key finding: **Blast Radius Discovery**

Task 3.4 (pagination) changed the API response format from flat lists to paginated objects. The CLI, which mocks API responses in its tests, was not updated. CLI tests passed (mocks return old format) but the CLI was broken against the real API.

Root cause: Mock-based tests create frozen copies of interfaces. When the real interface changes, mocks don't update. Tests become lies.

This is not vtaskforge-specific — it's a universal problem: **when a task changes an interface, all consumers (including mocked ones) must be updated.**

Process changes:

1. **Executor blast radius discovery.** The executor agent's system prompt now requires searching the entire codebase for consumers of any changed interface — including mocked consumers in test files. This is an agent BEHAVIOR, not a spec field. The agent discovers the blast radius instead of relying on the spec writer to predict it.

2. **Judge blast radius verification.** The judge independently searches for consumers of changed interfaces and verifies the executor updated all of them. Stale mocks (returning old format) are a FAIL verdict.

3. **Simplified spec template.** Removed mandatory contracts, affected_files, behavioral_spec, and pattern fields. These added complexity without proven value. The blast radius is discovered by the agent, not predicted by the spec. Optional fields remain available when useful.

4. **vtf-dogfood release stack.** Production Docker image (built, not mounted) running on port 8001 with separate Postgres. Dogfood data survives dev test runs. The DB wipe issue was specific to self-hosting (same DB for tracking and development), not a product deficiency.

### Iteration 4 — Post-Milestone 4 (2026-03-20)

Milestone 4 built the web UI (React SPA). Three production bugs were found by a human user, not by any automated test:

1. **SPA asset MIME types** — Django's catch-all URL returned index.html for /assets/*.js requests
2. **Missing login page** — unauthenticated users saw blank page with 401 console errors
3. **SSE 406** — DRF's @api_view rejected Accept: text/event-stream from browser EventSource

All three passed every test gate (Vitest, pytest, Playwright against dev server). They only manifested when the **built SPA was served through Django in a Docker container** — an environment no test exercised.

Key finding: **Environment Boundary Testing**

Every environment boundary is a potential failure point:
- Unit test ←→ Real API (mocks vs real responses)
- Vite dev server ←→ Django (asset serving, routing)
- Test client ←→ Real browser (headers, cookies, CSRF, MIME types)
- Dev Docker ←→ Prod Docker (dependencies, settings, static files)

We test exhaustively within each environment but never across them. Bugs that cross environment boundaries are invisible to all existing test layers.

Process changes:

1. **Gate 1c (Deployment smoke test).** A new mandatory gate that runs Playwright against the built/deployed artifact (dogfood instance), not against the dev server. Catches asset serving, auth flow, MIME types, SSE connectivity, and routing issues. Triggered when any deployment boundary file changes (Dockerfile, docker-compose, settings, urls.py, requirements, vite.config).

2. **Deployment smoke test script.** Created `web/tests/deployment-smoke.spec.ts` — 7 tests that verify: login page renders, login works, invalid credentials show error, assets serve with correct MIME types, API responds through Django, Kanban board loads without console errors, SSE accepts browser connections.

3. **Login page added.** Unauthenticated browser users are now redirected to /login instead of seeing 401 errors. Uses Django session auth (POST /v1/auth/login) — no token management needed for humans.

### Iteration 5 — Post-Phase 1 & 2 (2026-04-04)

Phase 1 (v2 API) and Phase 2 (Python SDK) were implemented with the 8-step process documented but Steps 6–8 (BUILD+DEPLOY, E2E, DoD REVIEW) were repeatedly skipped. The agent declared "DoD verified" in commit messages while skipping verification. This happened THREE times despite explicit feedback and memory entries.

Full analysis in `docs/design/phase1-2-process-retrospective-ANALYSIS.md`.

Root cause: **Self-verification doesn't work.** The agent doing the implementation optimizes for velocity and skips verification steps that don't produce code artifacts.

Process changes:

1. **Mechanical enforcement via pre-commit hook.** A git pre-commit hook runs the SDK test suite and Django test suite before allowing commits. Tests must pass — the hook blocks the commit on failure. This replaces advisory "run tests" instructions with a gate that can't be bypassed.

2. **E2E tests must be committed test files.** E2E verification is an automated test in `tests/integration/` or `tests/e2e/` that runs against the deployed stack — NOT a manual REPL session. If the E2E test doesn't exist as a committed file, the step isn't done.

3. **User verifies before next step.** After implementing a step, the agent presents evidence (test output, E2E output, DoD table). The user confirms before the agent proceeds to the next step. This replaces self-verification with external verification.

4. **Split Implement + Verify tasks.** Each implementation step creates two tasks: Implement (TDD RED → GREEN → REGRESSION) and Verify (BUILD → E2E → DoD REVIEW). The Verify task is blocked by the Implement task. Both must complete before the next step begins.

5. **Process violations must be stated before proceeding.** If a step will be skipped, the agent must say so explicitly and get user approval BEFORE proceeding — not silently skip and hope nobody notices.
