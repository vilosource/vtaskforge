# vtf MCP Server Specification

## 1. Overview

### Problem

LLM agents currently interact with vtf through the CLI via Bash tool calls:

```
LLM -> Bash("vtf task claim abc --agent executor-1 --tags python") -> parse text output
```

This requires shell overhead, text parsing, multi-step orchestration (claim, then show for spec, then list deps), and fragile error handling. Every interaction is a separate Bash invocation with context lost between calls.

### Solution

An MCP (Model Context Protocol) server embedded in the vtf Django application that exposes workflow-oriented tools. Agents get structured JSON responses enriched with decision context in a single round-trip.

```
LLM -> MCP tool(vtf_claim_and_start) -> structured JSON with task + spec + deps + test commands
```

### Target Users

- **Executor agents** — claim tasks, read specs, report progress, submit work
- **Supervisor agents** — view board state, find blockers, assign work, manage lifecycle
- **Judge agents** — review completed work, approve/reject with feedback
- **Human operators** — search tasks, manage lifecycle, get project overviews

## 2. Architecture

### Embedded in Django (Option B)

The MCP server runs inside the Django process, calling service layer functions directly. No HTTP round-trips for internal operations.

```
                    +-----------------+
                    |   Claude Code   |
                    |   (MCP Client)  |
                    +--------+--------+
                             |
                    MCP (stdio or streamable HTTP)
                             |
                    +--------+--------+
                    |  vtf MCP Server |
                    |  (Python SDK)   |
                    +--------+--------+
                             |
                    +--------+--------+
                    |  Service Layer  |  <-- shared with REST API
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
         +----+----+   +----+----+   +-----+-----+
         |  Models |   |  State  |   |  Events   |
         |   ORM   |   | Machine |   |  Service  |
         +---------+   +---------+   +-----------+
```

### Transport

- **stdio** — primary transport for Claude Code (local dev, agent execution)
- **Streamable HTTP** — future, for remote agents connecting over the network

### Service Layer (New)

Both REST views and MCP tools call the same service functions. Neither owns business logic.

```python
# src/tasks/services.py (new)
class TaskService:
    def claim(task_id, agent_id, tags) -> Task
    def find_claimable(project_id, tags) -> list[Task]
    def resolve_dependencies(task_id) -> DependencyStatus
    def transition(task_id, action, triggered_by) -> Task
    ...

# REST view becomes thin adapter:
def claim(self, request, pk):
    task = TaskService.claim(pk, request.data["agent_id"], request.data.get("tags"))
    return Response(TaskSerializer(task).data)

# MCP tool becomes thin adapter:
def vtf_claim_and_start(task_id, agent_id, tags):
    task = TaskService.claim(task_id, agent_id, tags)
    spec = task.spec
    deps = TaskService.resolve_dependencies(task_id)
    return enrich(task, spec=spec, deps=deps)
```

## 3. Prerequisites

Before MCP tools can be built, business logic must be extracted from views into a service layer.

### Phase 0: Service Layer Extraction

**P0.1 — TaskService** (extract from `src/tasks/views.py`)
- `claim()` — atomic claim with tag matching, dep checks, assignment validation (~110 lines)
- `find_claimable()` — query with dep resolution (currently duplicated in claim + claimable)
- `transition()` — wrapper around state_machine.perform_transition with event creation
- `resolve_dependencies()` — check Link table for unmet deps

**P0.2 — EventService** (extract from 5 duplicated locations)
- `record()` — central event creation, replaces try/catch blocks scattered in views

**P0.3 — ReviewService** (extract from `src/reviews/views.py`)
- `submit_review()` — decision routing (approved/rejected/changes_requested) + state transition

**P0.4 — Fix celery task**
- `expire_stale_claims()` must use TaskService.transition() instead of direct status mutation

**Already extracted (no work needed):**
- `tasks/state_machine.py` — transition validation + execution
- `tasks/review_policy.py` — review flag cascade
- `workplans/completion.py` — milestone auto-completion
- `core/bulk_import.py` — entity creation orchestration

## 4. Tool Contracts

### 4.1 Conventions

**Naming:** `vtf_{action}_{resource}` pattern.

**Parameters:** Flat, typed, with defaults. No nested dicts. Use string literals for enums.

**Responses:** Every response includes:
- `success: bool`
- `data: object` — the primary payload
- `available_actions: list[str]` — what the agent can do next
- `message: str` — human-readable summary (for errors: actionable guidance)

**Pagination:** List responses include `total_count`, `has_more`, `offset`, `limit`.

**Errors:** No raw tracebacks. Errors include what went wrong, why, and what to do instead.

```json
{
  "success": false,
  "message": "Task 'abc' is in 'blocked' status and cannot be claimed. Unblock it first or find another task.",
  "available_actions": ["vtf_search_tasks", "vtf_manage_task(action=unblock)"],
  "data": {"task_id": "abc", "current_status": "blocked"}
}
```

---

### 4.2 vtf_board_overview

**Purpose:** Get a high-level view of project state. Discovery layer — helps agents understand what needs attention.

**Description (for LLM):**
> Get a summary of the project board: task counts by status, blockers, tasks needing attention, and recent activity. Use this to understand the current state before deciding what to work on.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| project | string | no | configured default | Project ID |
| workplan | string | no | null | Filter to specific workplan |

**Response:**

```json
{
  "success": true,
  "data": {
    "project": {"id": "proj-1", "name": "vtaskforge"},
    "summary": {
      "total": 45,
      "by_status": {
        "draft": 3, "todo": 12, "doing": 4, "blocked": 2,
        "pending_start_review": 1, "pending_completion_review": 2,
        "changes_requested": 1, "needs_attention": 0,
        "done": 18, "cancelled": 2, "deferred": 0
      },
      "completion_pct": 40
    },
    "attention": [
      {"id": "t-1", "title": "Fix auth timeout", "status": "blocked", "reason": "Waiting on API key"},
      {"id": "t-2", "title": "Update schema", "status": "changes_requested", "reason": "Missing migration"}
    ],
    "pending_reviews": [
      {"id": "t-3", "title": "Add logging", "review_type": "completion", "waiting_since": "2026-03-24T10:00:00Z"}
    ],
    "active_agents": [
      {"agent": "executor-1", "task": "t-4", "title": "Implement caching", "claimed_at": "2026-03-24T09:30:00Z"}
    ]
  },
  "available_actions": ["vtf_next_work", "vtf_search_tasks", "vtf_task_detail", "vtf_manage_task"],
  "message": "Project vtaskforge: 45 tasks, 40% done. 2 blocked, 1 needs changes, 2 awaiting review."
}
```

---

### 4.3 vtf_next_work

**Purpose:** Find the best task for an agent to work on next. Planning layer — resolves dependencies and matches tags automatically.

**Description (for LLM):**
> Find the next task this agent should work on. Matches agent capabilities (tags) against task requirements, checks all dependencies are resolved, and returns the best candidate with full context. Use this instead of manually searching and checking dependencies.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| agent_id | string | yes | — | The agent's registered ID |
| tags | string | no | null | Comma-separated capability tags (e.g., "python,docker"). If omitted, uses agent's registered tags |
| project | string | no | configured default | Project ID |
| workplan | string | no | null | Filter to specific workplan |
| prefer | string | no | "priority" | Ordering: "priority" (milestone order), "newest", "oldest" |

**Response:**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-5",
      "title": "Add rate limiting middleware",
      "status": "todo",
      "milestone": {"id": "ms-2", "title": "Phase 2: API Hardening"},
      "labels": ["backend", "security"],
      "agent_model": "sonnet",
      "isolation": "worktree"
    },
    "spec_summary": "Add token-bucket rate limiting to all /v1/ endpoints. 100 req/min per token.",
    "dependencies": {
      "resolved": true,
      "tasks": [
        {"id": "t-3", "title": "Add logging", "status": "done"}
      ]
    },
    "alternatives": {
      "count": 4,
      "message": "4 other tasks are also claimable for your tags"
    }
  },
  "available_actions": ["vtf_claim_and_start", "vtf_search_tasks", "vtf_task_detail"],
  "message": "Recommended: 't-5: Add rate limiting middleware' (Phase 2, all deps resolved). 4 other options available."
}
```

**When no work is available:**

```json
{
  "success": true,
  "data": null,
  "available_actions": ["vtf_board_overview"],
  "message": "No claimable tasks matching tags ['python', 'docker']. 2 tasks are blocked, 1 has unresolved dependencies."
}
```

---

### 4.4 vtf_claim_and_start

**Purpose:** Claim a task and get everything needed to begin work. Execution layer — single round-trip to go from idle to working.

**Description (for LLM):**
> Claim a specific task and receive the full execution context: spec, dependencies, test commands, and isolation mode. After calling this, you have everything needed to start implementing. The task status will change to 'doing'.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| task_id | string | yes | — | Task ID to claim |
| agent_id | string | yes | — | Agent claiming the task |
| tags | string | no | null | Agent capability tags (comma-separated) |

**Response:**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-5",
      "title": "Add rate limiting middleware",
      "status": "doing",
      "claimed_by": "executor-1",
      "claim_expires_at": "2026-03-24T11:00:00Z"
    },
    "spec": "description: Add token-bucket rate limiting...\nfiles:\n  create:\n    - src/middleware/rate_limit.py\n  modify:\n    - src/vtaskforge/settings/base.py\n...",
    "dependencies": [
      {"id": "t-3", "title": "Add logging", "status": "done", "key_output": "Logging middleware at src/middleware/logging.py"}
    ],
    "test_command": {
      "unit": "pytest tests/test_rate_limit.py -v",
      "integration": "pytest tests/integration/ -k rate_limit"
    },
    "acceptance_criteria": [
      "Rate limiting returns 429 after 100 requests per minute",
      "Rate limit headers included in all responses",
      "Per-token tracking, not per-IP"
    ],
    "isolation": "worktree",
    "agent_model": "sonnet",
    "judge": true
  },
  "available_actions": ["vtf_report_progress", "vtf_submit_work", "vtf_manage_task(action=fail)", "vtf_manage_task(action=block)"],
  "message": "Claimed task t-5. Claim expires at 11:00 UTC. Judge review required on completion."
}
```

**Error — dependency not met:**

```json
{
  "success": false,
  "message": "Cannot claim task t-5: dependency t-3 ('Add logging') is in 'doing' status, not 'done'. Wait for it to complete or pick a different task.",
  "available_actions": ["vtf_next_work", "vtf_task_detail(task_id=t-3)"],
  "data": {"task_id": "t-5", "unresolved_deps": [{"id": "t-3", "status": "doing"}]}
}
```

---

### 4.5 vtf_report_progress

**Purpose:** Send a heartbeat and optionally add a note during execution. Keeps the claim alive and provides visibility.

**Description (for LLM):**
> Report progress on the task you're currently working on. This extends your claim timeout (preventing expiry) and optionally adds a note visible to supervisors. Call this periodically during long-running tasks.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| task_id | string | yes | — | Task ID being worked on |
| note | string | no | null | Progress note (e.g., "Tests passing, working on integration") |
| agent_id | string | no | null | Agent ID for the note's actor |

**Response:**

```json
{
  "success": true,
  "data": {
    "task_id": "t-5",
    "claim_expires_at": "2026-03-24T11:30:00Z",
    "note_added": true
  },
  "available_actions": ["vtf_report_progress", "vtf_submit_work", "vtf_manage_task(action=fail)"],
  "message": "Heartbeat received. Claim extended to 11:30 UTC. Note recorded."
}
```

---

### 4.6 vtf_submit_work

**Purpose:** Mark a task as complete, optionally triggering review. Handles the completion workflow in one call.

**Description (for LLM):**
> Submit your completed work on a task. If the task has review-on-completion enabled, it will move to 'pending_completion_review'. Otherwise it moves directly to 'done'. Optionally add a completion note describing what was done.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| task_id | string | yes | — | Task ID to complete |
| note | string | no | null | Completion summary (e.g., "Implemented rate limiting, all tests passing") |
| agent_id | string | no | null | Agent ID for the note's actor |

**Response:**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-5",
      "title": "Add rate limiting middleware",
      "status": "pending_completion_review"
    },
    "review_required": true,
    "milestone_progress": {
      "id": "ms-2",
      "title": "Phase 2: API Hardening",
      "completed": 5,
      "total": 8,
      "pct": 62
    }
  },
  "available_actions": ["vtf_next_work", "vtf_board_overview"],
  "message": "Task t-5 submitted for review (pending_completion_review). Milestone 'Phase 2' is now 62% complete."
}
```

---

### 4.7 vtf_search_tasks

**Purpose:** Find tasks by criteria with enriched results. Replaces raw list queries with contextual search.

**Description (for LLM):**
> Search for tasks matching specific criteria. Returns enriched results with status context and available actions for each task. Use filters to narrow results.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| status | string | no | null | Filter by status: draft, todo, doing, blocked, done, cancelled, deferred, needs_attention, pending_start_review, pending_completion_review, changes_requested |
| project | string | no | configured default | Project ID |
| workplan | string | no | null | Workplan ID |
| milestone | string | no | null | Milestone ID |
| labels | string | no | null | Comma-separated label filter |
| assigned_to | string | no | null | Agent ID |
| query | string | no | null | Text search in title and description |
| limit | integer | no | 20 | Max results (1-100) |
| offset | integer | no | 0 | Pagination offset |

**Response:**

```json
{
  "success": true,
  "data": {
    "tasks": [
      {
        "id": "t-5",
        "title": "Add rate limiting middleware",
        "status": "doing",
        "milestone": "Phase 2: API Hardening",
        "claimed_by": "executor-1",
        "labels": ["backend", "security"],
        "has_spec": true,
        "judge": true,
        "available_actions": ["vtf_task_detail"]
      }
    ],
    "total_count": 12,
    "has_more": true,
    "offset": 0,
    "limit": 20
  },
  "available_actions": ["vtf_task_detail", "vtf_search_tasks(offset=20)"],
  "message": "Found 12 tasks matching filters. Showing 1-12."
}
```

---

### 4.8 vtf_task_detail

**Purpose:** Deep-dive on a single task. Returns everything: spec, deps, reviews, events, and available transitions.

**Description (for LLM):**
> Get complete details for a specific task including its full spec, dependency status, review history, event timeline, and what actions are currently available. Use this when you need the full picture before acting on a task.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| task_id | string | yes | — | Task ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-5",
      "title": "Add rate limiting middleware",
      "description": "Token-bucket rate limiting for API endpoints",
      "status": "changes_requested",
      "project": {"id": "proj-1", "name": "vtaskforge"},
      "milestone": {"id": "ms-2", "title": "Phase 2: API Hardening"},
      "workplan": {"id": "wp-1", "title": "v1.0 Release"},
      "labels": ["backend", "security"],
      "assigned_to": "executor-1",
      "claimed_by": null,
      "created_by": "supervisor",
      "created_at": "2026-03-20T14:00:00Z",
      "updated_at": "2026-03-24T09:15:00Z"
    },
    "spec": "description: Add token-bucket rate limiting...",
    "acceptance_criteria": ["Rate limiting returns 429 after 100 req/min", "..."],
    "test_command": {"unit": "pytest tests/test_rate_limit.py -v"},
    "execution": {
      "agent_model": "sonnet",
      "judge": true,
      "isolation": "worktree"
    },
    "dependencies": {
      "depends_on": [{"id": "t-3", "title": "Add logging", "status": "done"}],
      "blocked_by_me": [{"id": "t-8", "title": "Load testing", "status": "todo"}],
      "all_resolved": true
    },
    "reviews": [
      {
        "decision": "changes_requested",
        "reason": "Missing rate limit headers in responses",
        "reviewer": "judge-1",
        "reviewer_type": "agent",
        "created_at": "2026-03-24T09:15:00Z"
      }
    ],
    "recent_events": [
      {"event": "status_changed", "from": "pending_completion_review", "to": "changes_requested", "at": "2026-03-24T09:15:00Z"},
      {"event": "review_submitted", "decision": "changes_requested", "by": "judge-1", "at": "2026-03-24T09:15:00Z"}
    ],
    "notes": [
      {"text": "Implemented core middleware, tests passing", "actor": "executor-1", "at": "2026-03-24T09:00:00Z"}
    ]
  },
  "available_actions": ["vtf_claim_and_start", "vtf_manage_task(action=block)", "vtf_manage_task(action=defer)", "vtf_manage_task(action=cancel)"],
  "message": "Task t-5 has changes requested: 'Missing rate limit headers in responses'. Ready to be reclaimed for rework."
}
```

---

### 4.9 vtf_manage_task

**Purpose:** Unified tool for task creation, updates, and lifecycle transitions. Reduces tool count by combining CRUD and state management.

**Description (for LLM):**
> Create, update, or change the status of a task. Use the 'action' parameter to specify the operation. For status changes, only valid transitions are allowed — the error message will tell you what transitions are available from the current status.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| action | string | yes | — | One of: create, update, submit, block, unblock, defer, cancel, delete, assign, unassign, reset |
| task_id | string | conditional | — | Required for all actions except 'create' |
| title | string | conditional | — | Required for 'create', optional for 'update' |
| project | string | conditional | — | Required for 'create' if no default configured |
| description | string | no | null | Task description |
| labels | string | no | null | Comma-separated labels |
| spec | string | no | null | Task spec (YAML text) |
| agent_model | string | no | null | Agent model override |
| judge | boolean | no | null | Enable judge review |
| isolation | string | no | null | Isolation mode: sequential, worktree |
| milestone | string | no | null | Milestone ID |
| workplan | string | no | null | Workplan ID |
| assigned_to | string | no | null | Agent ID (for 'assign' action) |
| reason | string | no | null | Reason (for 'block', 'reset' actions) |
| target_status | string | no | null | Target status (for 'reset' action only, admin) |

**Response (create example):**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-new",
      "title": "Add health check endpoint",
      "status": "draft"
    }
  },
  "available_actions": ["vtf_manage_task(action=submit)", "vtf_manage_task(action=update)", "vtf_task_detail"],
  "message": "Created task t-new in draft status. Submit it when ready for execution."
}
```

**Response (block example):**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-5",
      "title": "Add rate limiting middleware",
      "previous_status": "doing",
      "status": "blocked"
    }
  },
  "available_actions": ["vtf_manage_task(action=unblock)", "vtf_board_overview"],
  "message": "Task t-5 blocked (was 'doing'). Use unblock when the blocker is resolved."
}
```

**Error (invalid transition):**

```json
{
  "success": false,
  "message": "Cannot block task t-5: current status is 'done' (terminal). Terminal tasks cannot be transitioned. Use 'reset' with admin privileges to force a state change.",
  "available_actions": ["vtf_manage_task(action=reset)"],
  "data": {
    "task_id": "t-5",
    "current_status": "done",
    "valid_transitions": []
  }
}
```

---

### 4.10 vtf_review_task

**Purpose:** Submit a review decision for a task in review status. Used by judge agents and human reviewers.

**Description (for LLM):**
> Submit a review for a task that is awaiting review (pending_start_review or pending_completion_review). Approve to advance the task, or request changes with a reason explaining what needs to be fixed.

**Parameters:**

| Name | Type | Required | Default | Description |
|------|------|----------|---------|-------------|
| task_id | string | yes | — | Task ID to review |
| decision | string | yes | — | One of: approved, changes_requested, rejected |
| reason | string | conditional | — | Required for changes_requested and rejected |
| reviewer_id | string | no | "mcp-reviewer" | Reviewer identifier |
| reviewer_type | string | no | "agent" | One of: agent, human |

**Response (approved):**

```json
{
  "success": true,
  "data": {
    "task": {
      "id": "t-5",
      "title": "Add rate limiting middleware",
      "previous_status": "pending_completion_review",
      "status": "done"
    },
    "milestone_progress": {
      "id": "ms-2",
      "title": "Phase 2: API Hardening",
      "completed": 6,
      "total": 8,
      "pct": 75,
      "auto_completed": false
    }
  },
  "available_actions": ["vtf_board_overview", "vtf_next_work"],
  "message": "Task t-5 approved and marked done. Milestone 'Phase 2' is now 75% complete (6/8 tasks)."
}
```

## 5. Task Status Reference

For tool descriptions and error messages, the MCP server must understand the complete state machine.

### Statuses

| Status | Meaning | Terminal |
|--------|---------|---------|
| draft | Created, not yet submitted | no |
| pending_start_review | Awaiting approval to begin | no |
| todo | Ready to be claimed | no |
| doing | Claimed, in progress | no |
| pending_completion_review | Work done, awaiting review | no |
| changes_requested | Reviewer asked for rework | no |
| needs_attention | Agent reported failure | no |
| blocked | External blocker | no |
| deferred | Postponed | no |
| cancelled | Abandoned | yes |
| done | Completed | yes |

### Valid Transitions

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

## 6. Authentication

The MCP server reuses the existing vtf agent token system.

### For stdio transport (Claude Code)

The MCP server reads the agent token from vtf CLI config (`~/.vtf/config.yaml`) or environment variable `VTF_TOKEN`. No separate auth flow needed — if the agent is registered with vtf, its token works.

### For streamable HTTP transport (future)

Standard `Authorization: Token {token}` header, same as the REST API. The MCP server validates against Django's `authtoken` table.

### Agent registration

Agents register via the existing `POST /v1/agents/` endpoint (or a future `vtf_register_agent` MCP tool). Registration returns a token used for all subsequent MCP calls.

## 7. Implementation Phases

### Phase 0: Service Layer Extraction

Extract business logic from views into `src/tasks/services.py`, `src/events/services.py`, `src/reviews/services.py`. Both REST views and future MCP tools will call these services. This phase does not change any external behavior.

**Deliverables:**
- `src/tasks/services.py` — TaskService (claim, find_claimable, transition, resolve_deps)
- `src/events/services.py` — EventService (record)
- `src/reviews/services.py` — ReviewService (submit_review)
- Celery task fixed to use TaskService.transition()
- REST views refactored to call services
- All existing tests still pass

### Phase 1: MCP Server Skeleton

Set up the MCP server infrastructure using the Python MCP SDK.

**Deliverables:**
- MCP server entry point (`src/mcp_server/server.py`)
- Django integration (ORM access, settings loading)
- stdio transport working
- Auth middleware (token from config/env)
- `vtf_board_overview` tool as proof of concept
- Integration test: Claude Code can connect and call the tool

### Phase 2: Core Agent Workflow Tools

The tools executor agents need for the claim-work-submit cycle.

**Deliverables:**
- `vtf_next_work`
- `vtf_claim_and_start`
- `vtf_report_progress`
- `vtf_submit_work`
- Response enrichment (available_actions, dependency context)

### Phase 3: Management and Review Tools

Tools for supervisors, judges, and general task management.

**Deliverables:**
- `vtf_search_tasks`
- `vtf_task_detail`
- `vtf_manage_task`
- `vtf_review_task`

### Phase 4: Polish and Documentation

**Deliverables:**
- Error message quality pass (all errors actionable)
- MCP server README with setup instructions
- Claude Code `.mcp.json` config for vtf
- Performance testing (response times, concurrent access)
- Streamable HTTP transport (stretch goal)

## 8. Out of Scope

- **Workplan/milestone management via MCP** — manage via REST API or CLI for now
- **Bulk import via MCP** — use `vtf import` CLI command
- **Agent registration via MCP** — use REST API `POST /v1/agents/`
- **Real-time notifications** — MCP does not push events; agents poll via `vtf_board_overview`
- **Multi-tenant isolation** — single-tenant deployment assumed
- **MCP resources/prompts** — tools only for v1; resources (board state) and prompts (workflow templates) are future considerations
