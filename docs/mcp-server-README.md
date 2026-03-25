# vtf MCP Server

The vtf MCP (Model Context Protocol) server exposes vtaskforge as a structured tool interface for LLM agents. Instead of spawning shell processes to run `vtf` CLI commands and parsing text output, agents call MCP tools and receive structured JSON responses with full execution context in a single round-trip.

## Overview

### Who is it for

- **Executor agents** — claim tasks, read specs, report progress, submit work
- **Supervisor agents** — view board state, find blockers, assign work, manage lifecycle
- **Judge agents** — review completed work, approve or request changes
- **Human operators** — search tasks, manage lifecycle, get project overviews

### What it replaces

Before MCP:
```
LLM -> Bash("vtf task claim abc --agent executor-1") -> parse text
LLM -> Bash("vtf task show abc --json") -> parse JSON
LLM -> Bash("vtf task list --status todo") -> parse text
```

With MCP:
```
LLM -> vtf_claim_and_start(task_id="abc", agent_id="executor-1")
     -> structured JSON with task + spec + deps + test commands
```

### Architecture

The MCP server runs embedded in the Django application process. Tools call the same service layer functions used by the REST API — no HTTP overhead for internal operations.

```
Claude Code (MCP Client)
        |
   MCP (stdio)
        |
  vtf MCP Server (FastMCP)
        |
  Service Layer (tasks.services, reviews.services, events.services)
        |
  Django ORM + Postgres
```

The server uses auto-discovery: any Python module placed in `src/mcp_server/tools/` is automatically imported at startup. Tool functions decorated with `@mcp.tool()` are registered without any manual import lines in `server.py`.

## Setup

### Prerequisites

The vtf Docker stack must be running:

```bash
docker compose up -d
```

### Configure Claude Code

Copy the `.mcp.json` from the repo root to your Claude Code workspace, or add the `vtf` entry to your existing `.mcp.json`:

```json
{
  "mcpServers": {
    "vtf": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "api", "python", "-m", "mcp_server.server"],
      "env": {}
    }
  }
}
```

This runs the MCP server inside the `api` container via stdio transport. The `-T` flag disables TTY allocation, which is required for MCP stdio communication.

### Verify the connection

After adding `.mcp.json`, Claude Code will show `vtf` in its MCP tool list. You can test by asking Claude to call `vtf_board_overview`.

### Authentication

The MCP server uses the same agent token system as the REST API. Agents register via:

```bash
vtf agent register --name "my-agent" --tags executor,sonnet
```

The returned token can be passed as the `VTF_TOKEN` environment variable, or tools will operate in unauthenticated mode (same as CLI usage in the dev environment).

## Tool Reference

All tools return a JSON string with this envelope:

```json
{
  "success": true,
  "data": { ... },
  "message": "Human-readable summary for the agent",
  "available_actions": ["vtf_next_work", "vtf_board_overview"]
}
```

On error, `success` is `false` and `message` contains actionable guidance:

```json
{
  "success": false,
  "message": "Cannot claim task abc: dependency xyz is in 'doing' status. Wait for it to complete or use vtf_next_work to pick a different task.",
  "data": { "task_id": "abc", "dependency_id": "xyz" },
  "available_actions": ["vtf_next_work"]
}
```

---

### vtf_board_overview

Get a high-level summary of the project board: task counts by status, items needing attention, pending reviews, and active agents. Use this first to understand overall project state.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `project_id` | string | no | `""` | Filter to a specific project |
| `workplan_id` | string | no | `""` | Filter to a specific workplan |

**Example call:**
```
vtf_board_overview()
vtf_board_overview(workplan_id="wp-abc123")
```

**Returns:** Summary with `by_status` counts, attention items (blocked/needs_attention/changes_requested), pending reviews, and active agent assignments.

---

### vtf_next_work

Find the best available task for an agent to work on next. Checks dependency resolution and matches agent capability tags against task requirements automatically.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `agent_id` | string | no | `""` | Agent's registered ID |
| `tags` | string | no | `""` | Comma-separated capability tags (e.g., `"python,docker"`) |
| `project_id` | string | no | `""` | Filter to a specific project |

**Example call:**
```
vtf_next_work(agent_id="executor-1", tags="python,backend")
```

**Returns:** The recommended task with spec summary, dependency status, and count of alternative claimable tasks. Returns `data: null` with a helpful message if no work is available.

---

### vtf_claim_and_start

Claim a specific task and receive full execution context in one call. After this, the agent has everything needed to begin implementation: spec, dependencies, test commands, acceptance criteria, and isolation mode. The task moves to `doing` status.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | yes | — | Task ID to claim |
| `agent_id` | string | yes | — | Agent claiming the task |
| `tags` | string | no | `""` | Agent capability tags (comma-separated) |

**Example call:**
```
vtf_claim_and_start(task_id="t-abc123", agent_id="executor-1", tags="python")
```

**Returns:** Task info (including `claim_expires_at`), full `spec` YAML, dependency list, `test_command`, `acceptance_criteria`, `isolation` mode, `agent_model`, and `judge` flag.

**Errors:** Returns actionable errors for tag mismatch, unmet dependencies, or task already claimed.

---

### vtf_report_progress

Send a heartbeat during long-running tasks. Extends the claim timeout to prevent expiry and optionally records a progress note visible to supervisors. Call this periodically if a task will take more than the default claim timeout (30 minutes).

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | yes | — | Task ID being worked on |
| `note` | string | no | `""` | Progress note (e.g., `"Tests passing, working on integration"`) |
| `agent_id` | string | no | `""` | Agent ID for the note's actor |

**Example call:**
```
vtf_report_progress(task_id="t-abc123", note="Halfway through — unit tests passing", agent_id="executor-1")
```

**Returns:** Updated `claim_expires_at` and confirmation of whether a note was recorded.

---

### vtf_submit_work

Mark a task as complete. If the task has `judge: true` (review on completion enabled), the task moves to `pending_completion_review`. Otherwise it moves directly to `done`. Optionally include a completion note.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | yes | — | Task ID to complete |
| `completion_note` | string | no | `""` | Completion summary (e.g., `"All tests passing, committed on branch task/abc"`) |
| `agent_id` | string | no | `""` | Agent ID for the note's actor |

**Example call:**
```
vtf_submit_work(task_id="t-abc123", completion_note="Implemented and committed. 12 tests passing.", agent_id="executor-1")
```

**Returns:** New task status, whether review is required, and milestone progress (if task belongs to a milestone).

---

### vtf_search_tasks

Find tasks by criteria with enriched results. Supports multiple filters and text search. Results are paginated.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | no | `""` | Filter by status (see status reference below) |
| `project_id` | string | no | `""` | Project ID |
| `workplan_id` | string | no | `""` | Workplan ID |
| `milestone_id` | string | no | `""` | Milestone ID |
| `labels` | string | no | `""` | Comma-separated label filter (AND logic) |
| `assigned_to` | string | no | `""` | Agent ID |
| `query` | string | no | `""` | Text search in title and description |
| `limit` | integer | no | `20` | Max results (1–100) |
| `offset` | integer | no | `0` | Pagination offset |

**Example calls:**
```
vtf_search_tasks(status="todo", labels="backend")
vtf_search_tasks(query="rate limiting", workplan_id="wp-abc123")
vtf_search_tasks(status="doing", limit=50)
```

**Returns:** Paginated list of tasks with `total_count`, `has_more`, `offset`, `limit`. Each task includes `available_actions` for that specific task.

---

### vtf_task_detail

Get complete details for a single task: full spec, dependency status, review history, event timeline, progress notes, and available state-machine transitions.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | yes | — | Task ID |

**Example call:**
```
vtf_task_detail(task_id="t-abc123")
```

**Returns:** Full task fields, `spec` YAML, `acceptance_criteria`, `test_command`, `execution` settings (`agent_model`, `judge`, `isolation`), `dependencies` (resolved and blocking), `reviews` history, `recent_events` (last 10), and `notes` (progress/completion notes).

---

### vtf_manage_task

Unified tool for task creation, updates, and lifecycle transitions. Use the `action` parameter to specify the operation.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `action` | string | yes | — | Operation: `create`, `update`, `submit`, `block`, `unblock`, `defer`, `cancel`, `delete`, `assign`, `unassign` |
| `task_id` | string | conditional | `""` | Required for all actions except `create` |
| `title` | string | conditional | `""` | Required for `create`; optional for `update` |
| `project_id` | string | conditional | `""` | Required for `create` |
| `description` | string | no | `""` | Task description |
| `labels` | string | no | `""` | Comma-separated labels |
| `spec` | string | no | `""` | Task spec (YAML text) |
| `agent_model` | string | no | `""` | Agent model override (e.g., `"sonnet"`, `"opus"`) |
| `judge` | string | no | `""` | Enable judge review: `"true"` or `"false"` |
| `isolation` | string | no | `""` | Isolation mode: `"sequential"` or `"worktree"` |
| `milestone_id` | string | no | `""` | Milestone ID |
| `assigned_to` | string | no | `""` | Agent ID (for `assign` action) |
| `reason` | string | no | `""` | Reason text (for `block` action) |

**Actions and when to use them:**

| Action | What it does | Key params |
|--------|--------------|------------|
| `create` | Create a new task in `draft` status | `title`, `project_id` |
| `update` | Update mutable fields | `task_id` + any field |
| `submit` | Transition `draft` → `todo` | `task_id` |
| `block` | Transition to `blocked` | `task_id`, `reason` |
| `unblock` | Transition `blocked` → `todo` | `task_id` |
| `defer` | Transition to `deferred` | `task_id` |
| `cancel` | Transition to `cancelled` | `task_id` |
| `delete` | Delete the task | `task_id` |
| `assign` | Set `assigned_to` | `task_id`, `assigned_to` |
| `unassign` | Clear `assigned_to` | `task_id` |

**Example calls:**
```
vtf_manage_task(action="create", title="Add health check", project_id="proj-1")
vtf_manage_task(action="submit", task_id="t-abc123")
vtf_manage_task(action="block", task_id="t-abc123", reason="Waiting for API key from ops")
vtf_manage_task(action="assign", task_id="t-abc123", assigned_to="executor-1")
```

**Invalid transition errors** include the valid transitions from the current status so the agent knows what is possible.

---

### vtf_review_task

Submit a review decision for a task in `pending_start_review` or `pending_completion_review` status. Used by judge agents and human reviewers.

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `task_id` | string | yes | — | Task ID to review |
| `decision` | string | yes | — | One of: `approved`, `changes_requested`, `rejected` |
| `reason` | string | conditional | `""` | Required for `changes_requested` and `rejected` |
| `reviewer_id` | string | no | `"mcp-reviewer"` | Reviewer identifier |
| `reviewer_type` | string | no | `"agent"` | One of: `agent`, `human` |

**Example calls:**
```
vtf_review_task(task_id="t-abc123", decision="approved", reviewer_id="judge-1")
vtf_review_task(task_id="t-abc123", decision="changes_requested", reason="Missing error handling in edge cases", reviewer_id="judge-1")
```

**Decision outcomes:**
- `approved`: Task advances (`pending_completion_review` → `done`, `pending_start_review` → `todo`)
- `changes_requested`: Task moves to `changes_requested` status for rework
- `rejected`: Task moves to `cancelled`

**Returns:** Updated task status, previous status, and milestone progress if applicable.

---

## Response Format

Every tool returns a JSON string (not a Python dict) with this standard envelope:

```json
{
  "success": true | false,
  "data": { ... },
  "message": "Human-readable summary",
  "available_actions": ["vtf_tool_name", "vtf_other_tool(param=value)"]
}
```

**`success`** — Boolean. `false` indicates an error; `message` will explain what went wrong and what to do.

**`data`** — The primary payload. Structure varies by tool. May be `null` for no-result cases (e.g., `vtf_next_work` when nothing is available).

**`message`** — Plain-text summary written for the agent. For errors, it includes what went wrong, why, and what action to take next. For success, it summarizes the outcome.

**`available_actions`** — Suggestions for what to call next. Format is the tool name, optionally with parameters pre-filled: `"vtf_search_tasks(offset=20)"` or `"vtf_manage_task(action=unblock)"`. These are hints, not instructions.

### Pagination fields (list responses)

List responses from `vtf_search_tasks` include these fields inside `data`:

```json
{
  "tasks": [...],
  "total_count": 45,
  "has_more": true,
  "offset": 0,
  "limit": 20
}
```

Use `has_more` to decide whether to call again with an incremented `offset`.

## Error Handling

### Structured errors

All errors follow the same envelope format with `success: false`. Errors include:
- What went wrong
- Why it happened
- What to do instead (in `message`)
- Relevant context (in `data`, e.g., `current_status`, `valid_transitions`)
- Suggested next actions (in `available_actions`)

### Common error patterns

**Task not found:**
```json
{
  "success": false,
  "message": "Task abc123 not found.",
  "data": { "task_id": "abc123" },
  "available_actions": ["vtf_next_work"]
}
```

**Invalid state transition:**
```json
{
  "success": false,
  "message": "Cannot cancel task abc123: current status is 'done'. Valid transitions: [].",
  "data": { "task_id": "abc123", "current_status": "done", "valid_transitions": [] },
  "available_actions": ["vtf_manage_task"]
}
```

**Dependency not met (vtf_claim_and_start):**
```json
{
  "success": false,
  "message": "Cannot claim task abc123: dependency xyz is in 'doing' status, not 'done'. Wait for it to complete or use vtf_next_work to pick a different task.",
  "data": { "task_id": "abc123", "dependency_id": "xyz", "dependency_status": "doing" },
  "available_actions": ["vtf_next_work", "vtf_task_detail(task_id=xyz)"]
}
```

### available_actions pattern

The `available_actions` list is the MCP server's guidance system. After any call — success or failure — the server suggests the logical next steps. Agents should treat these as context-aware recommendations, not hard constraints. They are especially useful for recovering from errors without needing to know the full state machine.

## Task Status Reference

| Status | Meaning | Terminal |
|--------|---------|---------|
| `draft` | Created, not yet submitted for execution | no |
| `pending_start_review` | Awaiting approval to begin work | no |
| `todo` | Ready to be claimed | no |
| `doing` | Claimed by an agent, in progress | no |
| `pending_completion_review` | Work submitted, awaiting review | no |
| `changes_requested` | Reviewer requested rework | no |
| `needs_attention` | Agent reported failure | no |
| `blocked` | External blocker preventing progress | no |
| `deferred` | Postponed | no |
| `cancelled` | Abandoned (terminal) | yes |
| `done` | Completed (terminal) | yes |

### Valid transitions

```
draft                     -> pending_start_review, todo, cancelled, deferred
pending_start_review      -> todo, changes_requested, cancelled, deferred
todo                      -> doing, blocked, cancelled, deferred
doing                     -> todo, pending_completion_review, done, needs_attention, blocked, cancelled, deferred
pending_completion_review -> done, changes_requested, cancelled, deferred
changes_requested         -> doing, pending_start_review, pending_completion_review, draft, cancelled, deferred
needs_attention           -> draft, todo, cancelled, deferred
blocked                   -> todo, doing, cancelled, deferred
deferred                  -> todo, cancelled
cancelled                 -> (terminal)
done                      -> (terminal)
```

## Architecture

### Embedded in Django

The MCP server lives at `src/mcp_server/` inside the Django project. It bootstraps Django at startup (`django.setup()`), then creates a FastMCP instance. All tool implementations call service layer functions directly — no HTTP requests for internal operations.

```
src/
  mcp_server/
    server.py          # Entry point, FastMCP instance, auto-discovery
    auth.py            # Token validation against Django authtoken table
    responses.py       # success_response() and error_response() helpers
    tools/
      __init__.py
      board.py         # vtf_board_overview
      workflow.py      # vtf_next_work, vtf_claim_and_start, vtf_report_progress, vtf_submit_work
      search.py        # vtf_search_tasks
      detail.py        # vtf_task_detail
      manage.py        # vtf_manage_task
      review.py        # vtf_review_task
```

### Service layer

MCP tools and REST views both call the same service functions. Neither layer owns business logic.

```python
# Both of these call the same service function:
# REST view:
class ClaimView(APIView):
    def post(self, request, pk):
        claim_task(pk, request.data["agent_id"], ...)

# MCP tool:
def vtf_claim_and_start(task_id, agent_id, ...):
    claim_task(task_id, agent_id, ...)
```

### Auto-discovery

Tools are auto-discovered at startup — no manual import lines needed. To add a new tool module:

1. Create `src/mcp_server/tools/my_tool.py`
2. Import FastMCP and the server instance: `from mcp_server.server import mcp`
3. Decorate your function: `@mcp.tool()`
4. It will be registered automatically the next time the server starts

```python
# src/mcp_server/tools/my_tool.py
import json
from mcp_server.server import mcp
from mcp_server.responses import success_response

@mcp.tool()
def vtf_my_tool(param: str) -> str:
    """Tool description shown to the LLM."""
    result = some_service_function(param)
    return json.dumps(success_response(data=result, message="Done."))
```

The server discovers all modules in `mcp_server/tools/` via `pkgutil.iter_modules` and imports them before the server starts listening.

## Troubleshooting

### MCP server not appearing in Claude Code

Check that `.mcp.json` is in the project root and the `vtf` entry uses the correct `docker compose exec` command. The container name must match your active compose file (`api` in dev, `dogfood-api` in dogfood).

### "docker compose exec" fails

Verify the `api` container is running:
```bash
docker compose ps
```

If the container is stopped, start it:
```bash
docker compose up -d
```

### Tools return Django setup errors

The MCP server requires Django to be fully initialized. If you see `Apps aren't loaded yet` or similar, it usually means the server is being imported before `django.setup()` is called. This should not happen in normal usage — the entry point in `server.py` calls `django.setup()` at module level before any tool imports.

### Database connection errors

If tools fail with `OperationalError: could not connect to server`, Postgres may not be running:
```bash
docker compose up -d db
docker compose restart api
```

### Tool not found after adding a new module

Auto-discovery runs once at startup. If you added a new tool module while the server was running, restart the container:
```bash
docker compose restart api
```

### Claim expiry errors

Task claims expire after the task's configured timeout (default 30 minutes). If a claim expires while working, the task reverts to `todo`. Call `vtf_report_progress` periodically to extend the claim. If the claim has already expired, use `vtf_claim_and_start` to re-claim (if no other agent has picked it up).

### Dogfood instance

To connect Claude Code to the dogfood instance instead of the dev stack, change the container name in `.mcp.json`:

```json
{
  "mcpServers": {
    "vtf": {
      "command": "docker",
      "args": ["compose", "-f", "docker-compose.dogfood.yml", "exec", "-T", "dogfood-api", "python", "-m", "mcp_server.server"],
      "env": {}
    }
  }
}
```

## Development: Adding a New Tool

1. Create `src/mcp_server/tools/<name>.py`
2. Use `success_response` / `error_response` from `mcp_server.responses`
3. Keep tool functions thin — call service layer, format response
4. Use `available_actions` to guide the agent toward logical next steps
5. Never return raw tracebacks — catch exceptions and return `error_response` with actionable guidance
6. Restart the container so auto-discovery picks up the new module

For full design context and the original specification, see:
- `docs/vtf-mcp-server-SPECIFICATION.md` — complete tool contracts, architecture decisions, and implementation phases
- `docs/vtf-mcp-server-IMPLEMENTATION-PLAN.md` — phased build plan with task breakdown
