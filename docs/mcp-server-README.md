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

Two transport modes are supported:

**stdio (local dev — Claude Code on same machine):**

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

**Streamable HTTP (remote agents — vafi executors, k8s pods):**

```
vafi Executor / k8s Pod
        |
   HTTP POST /mcp  (Authorization: Token <key>)
        |
  vtf MCP Server (uvicorn + Starlette + TokenAuthMiddleware)
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

### stdio transport (default — Claude Code on local machine)

Copy the `.mcp.json` from the repo root to your Claude Code workspace, or add the `vtf` entry to your existing `.mcp.json`:

```json
{
  "mcpServers": {
    "vtf": {
      "command": "docker",
      "args": ["compose", "exec", "-T", "api", "python", "src/mcp_server/server.py"],
      "env": {}
    }
  }
}
```

This runs the MCP server inside the `api` container via stdio transport. The `-T` flag disables TTY allocation, which is required for MCP stdio communication.

Note: the server must be started with `python src/mcp_server/server.py` (not `python -m mcp_server.server`) to avoid a double-import issue — see the Development section below.

### HTTP transport (remote agents)

The `mcp` service in `docker-compose.yml` runs the server in HTTP mode on port 8002. Start it alongside the API:

```bash
docker compose up -d mcp
```

Verify the server is reachable:

```bash
curl http://localhost:8002/health
```

Create an agent token for the remote client:

```bash
vtf agent register --name "my-remote-agent" --tags executor,sonnet
# Returns: token <key>
```

Remote agents then connect by sending MCP requests to `http://<host>:8002/mcp` with the header:

```
Authorization: Token <key>
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `VTF_MCP_TRANSPORT` | `stdio` | Transport mode: `stdio` or `http` |
| `VTF_MCP_HOST` | `0.0.0.0` | Bind address (HTTP mode only) |
| `VTF_MCP_PORT` | `8002` | Listen port (HTTP mode only) |

### Authentication

**stdio transport:** Authentication is not enforced. Tools operate against the Django database directly without a token check. This matches the dev CLI behavior.

**HTTP transport:** All requests (except `GET /` and `GET /health`) must include an `Authorization: Token <key>` header. The token is validated against the Django authtoken table. Requests without a valid token receive a `401` response.

Create a token via the vtf CLI:

```bash
vtf agent register --name "my-agent" --tags executor,sonnet
# Returns the token to use in Authorization headers
```

The returned token must be set on the remote agent, for example as an environment variable:

```bash
export VTF_TOKEN=<key>
```

Tool implementations can read this value to include in outbound MCP calls.

### Remote agent configuration

**vafi executor containers:** Connect to the MCP service using its Docker Compose service name:

```
http://vtf-mcp:8002/mcp
```

The service name resolves automatically within a shared Docker network. Set `Authorization: Token <key>` using the agent's registered token.

**Kubernetes internal:** Use the Kubernetes service DNS:

```
http://vtf-mcp.<namespace>.svc.cluster.local:8002/mcp
```

**External access:** Expose the service via ingress and configure your ingress controller to route `<host>/mcp` to port 8002 on the mcp pod.

### Verify the connection

After adding `.mcp.json` (stdio), Claude Code will show `vtf` in its MCP tool list. You can test by asking Claude to call `vtf_board_overview`.

For HTTP transport, verify with a direct curl (replace `<token>` with a valid agent token):

```bash
curl -H "Authorization: Token <token>" http://localhost:8002/mcp
```

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

> **Legacy tool — prefer the decomposed Phase 4c tools for new work.**
> `vtf_manage_task` remains available for compatibility, but every
> `action` now has a dedicated tool:
>
> | Legacy | Replacement |
> |--------|-------------|
> | `action="create"` | `vtf_create_task` (supports `depends_on` for Link-based task dependencies) |
> | `action="update"` | `vtf_update_task` (supports `depends_on` with REPLACE semantics) |
> | `action="submit"` | `vtf_submit_task` |
> | `action="block"` | `vtf_block_task` |
> | `action="unblock"` | `vtf_unblock_task` |
> | `action="defer"` | `vtf_defer_task` |
> | `action="cancel"` | `vtf_cancel_task` |
> | `action="delete"` | `vtf_delete_task` |
> | `action="assign"` | `vtf_assign_task` |
> | `action="unassign"` | `vtf_unassign_task` |
>
> See `docs/design/phase4c-mcp-redesign-DESIGN.md` for the rationale.

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

### vtf_create_link / vtf_delete_link

Manage cross-entity Links (the row-level table that models task-to-task
dependencies and other relationships). Use these when wiring
`depends_on` between existing tasks, or linking tasks to external
references (commits, docs, jira tickets).

Creation is also available inline on task tools: `vtf_create_task(depends_on="<id>,<id>")`
and `vtf_update_task(depends_on="<id>,<id>")` both create Link rows
automatically — use `vtf_create_link` when you need a non-`depends_on`
type or are linking to a non-task target.

**vtf_create_link parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `source_type` | string | yes | One of `task`, `workplan`, `milestone` |
| `source_id` | string | yes | ID of the source entity |
| `target_type` | string | yes | Entity type — typically `task`; free-form for external refs (`commit`, `doc`, `jira`, `file`) |
| `target_id` | string | yes | ID or URL of the target |
| `link_type` | string | yes | One of `depends_on`, `blocks`, `relates_to`, `commit`, `mr`, `area`, `doc`, `file`, `jira` |
| `metadata` | string | no | Optional JSON object |

**vtf_delete_link parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `link_id` | string | yes | Link id to delete |

Both tools enforce project membership — the caller's user must be a
member of the source entity's project (staff bypass).

**Examples:**
```
# Make t-b depend on t-a
vtf_create_link(source_type="task", source_id="t-b", target_type="task", target_id="t-a", link_type="depends_on")

# Remove a dependency
vtf_delete_link(link_id="l-xyz")

# Link a task to a commit for audit trail
vtf_create_link(source_type="task", source_id="t-a", target_type="commit", target_id="abc1234", link_type="commit")
```

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
    server.py          # Entry point, FastMCP instance, auto-discovery, transport selection
    auth.py            # Token validation against Django authtoken table
    http_auth.py       # Starlette TokenAuthMiddleware for HTTP transport
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

## E2E Testing

The vtf MCP server has an end-to-end test suite that exercises the full stack: Postgres, the Django API, and the MCP server together in an isolated Docker environment.

### What the tests cover

Four test scenarios verify the MCP server's behavior end-to-end:

1. **Executor workflow** — claim a task, report progress, and submit work; verifies the full executor lifecycle through MCP tools
2. **Supervisor workflow** — board overview, find next available task, and lifecycle management via `vtf_manage_task`
3. **Task lifecycle** — transitions through all major states (draft → todo → doing → done) using MCP tools
4. **Error handling** — invalid transitions, missing tasks, unmet dependencies, and bad auth tokens return structured errors

### How to run

From the repo root:

```bash
./scripts/run-e2e.sh
```

The script:
1. Brings up an isolated stack (db + api + mcp) using `docker-compose.e2e.yml`
2. Runs Django migrations and seeds test data
3. Waits for the MCP server to become ready
4. Runs `pytest tests/e2e/ -v --tb=short`
5. Tears down the stack on exit (success or failure)

Exit code reflects test results — zero on pass, non-zero on failure.

### Isolated stack details

| Service | Host port | Notes |
|---------|-----------|-------|
| api | 18000 | Django runserver, E2E settings |
| mcp | 18002 | HTTP transport mode |
| db | (internal) | Ephemeral — tmpfs, destroyed on teardown |

The E2E database (`vtf_e2e`) is completely separate from dev and dogfood. It is destroyed when the stack is torn down, so each run starts clean.

### Debugging failures

If the tests fail, inspect the container logs before the stack tears down by opening a second terminal:

```bash
docker compose -f docker-compose.e2e.yml -p vtf-e2e logs
docker compose -f docker-compose.e2e.yml -p vtf-e2e logs api
docker compose -f docker-compose.e2e.yml -p vtf-e2e logs mcp
```

To keep the stack running after a failure for manual inspection, run the script steps individually instead of using `run-e2e.sh`:

```bash
docker compose -f docker-compose.e2e.yml -p vtf-e2e up -d --build --wait
docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api python src/manage.py migrate --run-syncdb
docker compose -f docker-compose.e2e.yml -p vtf-e2e exec -T api python -c "exec(open('/app/tests/e2e/seed.py').read())"
pytest tests/e2e/ -v --tb=short
# Inspect logs, then tear down manually:
docker compose -f docker-compose.e2e.yml -p vtf-e2e down -v
```

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
      "args": ["compose", "-f", "docker-compose.dogfood.yml", "exec", "-T", "dogfood-api", "python", "src/mcp_server/server.py"],
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

### Double-import issue with `python -m`

When the server is run via `python -m mcp_server.server`, Python imports the module twice: once as `__main__` and once as `mcp_server.server`. This means tool registrations on the `mcp` instance in `mcp_server/tools/*.py` (imported as `from mcp_server.server import mcp`) go to a different `mcp` instance than the one that actually runs. The tools are silently not registered.

The fix is to run the server directly as a script, not as a module:

```bash
# Correct — tools register on the running instance
python src/mcp_server/server.py

# Broken — double-import causes tools to be on the wrong mcp instance
python -m mcp_server.server
```

The `docker-compose.yml` `mcp` service and the `.mcp.json` stdio configuration both use the script form to avoid this. If you encounter a situation where the server starts but no tools are visible, check how the server process was invoked.

For full design context and the original specification, see:
- `docs/vtf-mcp-server-SPECIFICATION.md` — complete tool contracts, architecture decisions, and implementation phases
- `docs/vtf-mcp-server-IMPLEMENTATION-PLAN.md` — phased build plan with task breakdown
