# vtf MCP & CLI Improvements Plan

## Context

This plan was produced during a session on 2026-03-26 where we used the vtf MCP
tools to manage backlog tasks on the production instance (vtf.viloforge.com).
The session involved:

1. Reviewing the backlog (16 draft tasks)
2. Verifying and cancelling 2 stale bug tickets (kanban pending_completion_review,
   SSE postgres pool — both already fixed in code)
3. Creating a "Web UI UX Improvements" workplan with 5 breadcrumb/navigation tasks
4. Attempting to move those tasks into the new workplan

The last step exposed significant friction in the MCP and CLI tooling, which
prompted a full retrospective.

## What Works Well (Keep As-Is)

The **task execution cycle** is solid — this was the primary design target for
agent simulation and it shows:

- `vtf_next_work` → `vtf_claim_and_start` → `vtf_report_progress` → `vtf_submit_work` → `vtf_review_task`
- State machine transitions are well-enforced with helpful error messages
- Read tools (`vtf_board_overview`, `vtf_search_tasks`, `vtf_task_detail`) return
  rich, structured data with available_actions hints

No changes needed for this path.

## Friction Points Encountered

### 1. Can't assign tasks to a workplan via MCP

**What happened:** Created 5 tasks via `vtf_manage_task(action=create)` — they
all landed as orphan backlog tasks because there's no `workplan_id` parameter.

**Workaround:** kubectl exec into the prod API pod, ran Django ORM commands to
set `task.workplan` directly.

**Decision context:** The MCP `create` action does support `milestone_id` which
auto-sets the workplan (since milestones belong to workplans). But we had just
created the workplan and had no milestones yet. Even if milestones existed, you
shouldn't need one just to put a task in a workplan — backlog tasks within a
workplan are a valid pattern (task belongs to workplan, no milestone yet).

### 2. Can't move tasks between workplans via MCP or CLI

**What happened:** After creating tasks, tried:
- MCP `vtf_manage_task(action=update)` — no `workplan_id` param
- CLI `vtf task update --workplan` — no such flag
- Direct API PATCH via curl — blocked by CSRF (see #3)

**Decision context:** The `update` action only supports `milestone_id` for
structural changes (which auto-sets workplan). Same limitation as create.

### 3. CSRF blocks token-authenticated API writes

**What happened:** curl PATCH with valid `Authorization: Token ...` header
returned 403 CSRF Forbidden. The prod settings enforce `CSRF_COOKIE_SECURE` and
`CSRF_TRUSTED_ORIGINS`, but DRF's `TokenAuthentication` should be CSRF-exempt
since it doesn't use cookies.

**Root cause:** Django's CSRF middleware runs before DRF's authentication.
Session-based auth needs CSRF, but token auth doesn't. The fix is to exempt
token-authenticated requests from CSRF, which DRF normally handles via
`SessionAuthentication.enforce_csrf()` — but the global CSRF middleware catches
it first.

**Impact:** This blocks all programmatic API writes from scripts, curl, and any
non-browser client that doesn't manage CSRF cookies.

### 4. No milestone CRUD in CLI or MCP

**What happened:** Wanted to create a milestone in the new workplan to organize
tasks. No `vtf milestone create` command exists (only `vtf milestone stats`).
No MCP tool for milestone management.

### 5. Action name mismatch in MCP

**What happened:** Tried `vtf_manage_task(action=cancelled)` — the status name
is "cancelled" but the action is "cancel". Error message was helpful ("Valid
actions: ...cancel...") but could be better with a direct suggestion.

**Decision context:** This is a minor DX issue. The convention is: actions are
verbs (cancel, block, defer), statuses are adjectives/past tense (cancelled,
blocked, deferred). Makes sense semantically, but easy to confuse since both
appear in the same tool.

## Gap Analysis: MCP manage_task vs Task Model

The Task model has fields that the MCP tool can't set. This table shows
every writable model field and whether it's exposed:

| Model Field                     | On MCP create | On MCP update | Notes |
|---------------------------------|---------------|---------------|-------|
| `title`                         | Yes           | Yes           | |
| `description`                   | Yes           | Yes           | |
| `project`                       | Yes           | No            | Can't move between projects |
| `workplan`                      | Via milestone | Via milestone  | **No direct assignment** |
| `milestone`                     | Yes           | Yes           | |
| `labels`                        | Yes           | Yes           | |
| `spec`                          | Yes           | Yes           | |
| `agent_model`                   | Yes           | Yes           | |
| `judge`                         | Yes           | Yes           | |
| `isolation`                     | Yes           | Yes           | |
| `assigned_to`                   | Via action    | Via action     | Separate assign/unassign actions |
| `acceptance_criteria`           | **No**        | **No**         | JSONField, list of strings |
| `requires`                      | **No**        | **No**         | JSONField, list of task IDs |
| `needs_review_before_start`     | **No**        | **No**         | Boolean |
| `needs_review_on_completion`    | **No**        | **No**         | Boolean, defaults to True |
| `test_command`                  | **No**        | **No**         | JSONField, dict |

**Decision context on missing fields:** These were omitted from the initial MCP
implementation (phase 3) because the simulation workflow didn't need them — specs
were pre-authored with all fields set via `vtf import`. But now that we're using
MCP for task authoring (not just execution), they're needed. The `acceptance_criteria`
and `requires` fields are particularly important for an agent that plans and
creates work.

## Missing Tools / Operations

| Operation                              | CLI | MCP | Impact |
|----------------------------------------|-----|-----|--------|
| Create workplan                        | Yes | No  | Can't set up work structure from MCP |
| List workplans                         | Yes | No  | Agent can't browse workplans |
| Update/archive workplan                | Yes | No  | |
| Create milestone                       | No  | No  | Can't organize work at all |
| List milestones (in a workplan)        | No  | No  | |
| Update/reorder milestones              | No  | No  | |
| Workplan tree view                     | No  | No  | No way to see workplan → milestones → tasks hierarchy |
| Move task to workplan (without milestone) | No | No | Most common organizational need |
| Add note to non-doing task             | No  | No  | `report_progress` requires task in `doing` status |
| Bulk task operations                   | No  | No  | N serial calls for batch work |

**Decision context on workplan/milestone management:** vtf was designed as a
"task coordination engine" with project-level concerns kept separate (see KB
gotcha: "vtf is a task coordination engine only"). But in practice, the agent
doing planning work IS the one creating workplans and milestones. The boundary
should be: vtf manages the work breakdown structure (project → workplan →
milestone → task), and anything above that (documents, team coordination) is
out of scope. Work structure management is firmly within vtf's scope.

## Improvement Themes

### Theme A: Complete manage_task parameter coverage

These are all small changes to `src/mcp_server/tools/manage.py` — adding params
to `_action_create()` and `_action_update()` that map to existing model fields.

1. **Add `workplan_id` to create + update**
   - Allow direct workplan assignment without requiring a milestone
   - On create: set `task.workplan` from workplan_id
   - On update: set `task.workplan`, optionally clear `task.milestone` if moving
     to a workplan that doesn't contain the current milestone
   - This is the single highest-impact change — would have eliminated the kubectl
     workaround entirely

2. **Add `acceptance_criteria` to create + update**
   - Accept as comma-separated string or JSON array
   - Maps to `task.acceptance_criteria` (JSONField, list of strings)

3. **Add `requires` (dependency list) to create + update**
   - Accept as comma-separated task IDs
   - Maps to `task.requires` (JSONField, list of task IDs)
   - Validate that referenced task IDs exist

4. **Add `needs_review_before_start` and `needs_review_on_completion` to create + update**
   - Accept as string booleans ("true"/"false"), same pattern as `judge`
   - Maps to boolean model fields

5. **Add `test_command` to create + update**
   - Accept as JSON string
   - Maps to `task.test_command` (JSONField, dict)
   - Format: `{"unit": "pytest tests/...", "integration": "..."}`

### Theme B: Work structure management

These require new MCP tool files and/or new CLI commands.

6. **New MCP tool: `vtf_manage_workplan`**
   - Actions: create, list, update, archive, complete
   - Create params: name, description, tags, project_id
   - List params: project_id, status filter
   - Returns: workplan with milestone count, task counts by status
   - **Decision context:** Considered adding workplan actions to `vtf_manage_task`
     but that tool is already overloaded with 10 actions. A separate tool keeps
     the scope clear and the docstring meaningful for LLM tool selection.

7. **New MCP tool: `vtf_manage_milestone`**
   - Actions: create, list, update, reorder, delete
   - Create params: name, workplan_id, sort_order, description
   - List params: workplan_id
   - Returns: milestone with task counts by status
   - **Decision context:** Same reasoning as workplan tool — separate concerns.

8. **Workplan tree view (extension to existing tool or new tool)**
   - Could be a new tool `vtf_workplan_tree` or an extension to `vtf_board_overview`
   - Returns: workplan → milestones (with sort_order) → task summaries per milestone
   - This is the "big picture" view an agent needs when planning work — understanding
     what exists before creating new tasks
   - **Decision context:** Considered adding a `tree` action to `vtf_manage_workplan`
     but a read-only view is conceptually different from management actions. Leaning
     toward a standalone `vtf_workplan_tree` tool since it would be frequently used
     and benefits from a clear, discoverable name.

### Theme C: CLI parity

These ensure the CLI can do everything the MCP can (and vice versa).

9. **`vtf task update` — add missing flags**
   - `--workplan` — assign task to workplan
   - `--milestone` — assign task to milestone (already supported in MCP but not CLI)
   - `--acceptance-criteria` — set criteria (JSON or repeated flag)
   - `--requires` — set dependencies (comma-separated task IDs)
   - `--test-command` — set test command (JSON string)
   - `--needs-review-before-start` / `--needs-review-on-completion` — boolean flags

10. **`vtf milestone` subcommands**
    - `vtf milestone create --name NAME --workplan WORKPLAN_ID [--sort-order N]`
    - `vtf milestone list --workplan WORKPLAN_ID`
    - `vtf milestone show MILESTONE_ID`
    - `vtf milestone update MILESTONE_ID --name/--sort-order`

### Theme D: Bug fixes

11. **CSRF exemption for token-authenticated API requests**
    - The Django CSRF middleware intercepts all non-safe requests before DRF auth
    - Fix: Add `@csrf_exempt` to API views, or configure DRF's
      `SessionAuthentication` as the only auth class that enforces CSRF
    - This is a well-known Django+DRF pattern — DRF's `SessionAuthentication`
      already has `enforce_csrf()` built in, but the global middleware overrides it
    - **Decision context:** This isn't just a DX issue — it blocks any non-browser
      integration. CI scripts, webhook handlers, and CLI tools all need token auth
      to work without CSRF.

12. **Better action name hints in MCP error messages**
    - When user sends `action=cancelled`, suggest `action=cancel`
    - Simple fuzzy match or mapping: strip common suffixes (ed, ing) and check
    - Low effort, high DX value for LLM callers that might use status names
      instead of action names

### Theme E: Quality of life

13. **Add note to any task regardless of status**
    - Currently `report_progress` only works on tasks in `doing` status
    - Need: annotate draft tasks during planning, add notes to blocked tasks
      explaining the blocker, add notes to todo tasks with context
    - Could be a new action on `vtf_manage_task` (e.g., `action=note`) or a
      standalone tool
    - **Decision context:** Using `manage_task(action=note)` keeps the tool count
      low but adds yet another action to an already-large tool. A standalone
      `vtf_add_note` tool might be cleaner since adding a note is conceptually
      different from managing task state.

14. **Bulk task operations**
    - Move multiple tasks to a workplan/milestone in one call
    - Bulk status transitions (e.g., submit all draft tasks in a milestone)
    - Accept comma-separated task IDs
    - **Decision context:** This is a convenience optimization. Without it, the
      agent makes N serial MCP calls which works but is slow. Lower priority than
      the other items — revisit after the single-task operations are complete.

## Implementation Order (Suggested)

The themes are independent and can be worked in any order. Within each theme,
the suggested order is:

1. **Theme D (bug fixes)** — CSRF fix unblocks direct API usage for all other work
2. **Theme A (manage_task params)** — highest-impact improvements, smallest changes
3. **Theme B (structure management)** — new tools, medium effort
4. **Theme C (CLI parity)** — mirrors MCP changes in CLI
5. **Theme E (quality of life)** — nice-to-have, do when convenient

## Files That Will Be Modified

### MCP tools (Theme A, B)
- `src/mcp_server/tools/manage.py` — add params to create/update
- `src/mcp_server/tools/workplan.py` — new file for workplan management
- `src/mcp_server/tools/milestone.py` — new file for milestone management
- `src/mcp_server/tools/structure.py` — new file for tree view (or extend board.py)

### CLI (Theme C)
- `src/cli/commands/task.py` — add flags to update command
- `src/cli/commands/milestone.py` — new file for milestone commands

### API (Theme D)
- `src/vtaskforge/settings/prod.py` — CSRF configuration
- `src/vtaskforge/urls.py` or API views — csrf_exempt decoration

### MCP error handling (Theme D)
- `src/mcp_server/tools/manage.py` — action name fuzzy matching

## Related Backlog Context

The following backlog items remain from the original 16 draft tasks (now 13
after cancelling 3: 2 fixed bugs + 1 replaced breadcrumb task). The 5 new
breadcrumb/navigation tasks are in the "Web UI UX Improvements" workplan
(`-E2i5pFHKIBk3BDNdCtnQ`).

This MCP/CLI improvements plan should become its own workplan when we're ready
to implement. It is independent of the UI work.
