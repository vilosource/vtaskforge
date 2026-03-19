# vtaskforge — API Surface Design

Status: Design (2026-03-19)

## Overview

REST API with OpenAPI spec, versioned via URL (`/v1/`). All communication is JSON over HTTPS. Real-time events via SSE.

Designed for these consumers:
- **vf-agents** (Go) — claim tasks, report results, heartbeat
- **Scrum Master Agent** — event stream, triage, metrics
- **Web UI** (SPA) — full CRUD, live updates, reviews
- **Terminal UI** (Node/TS) — same operations via CLI
- **Intake Tooling** — bulk creation of initiatives/phases/tasks
- **External Systems** — unblock tasks, future webhook support

## API Style Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Style | REST | Universal, any language can consume, great tooling |
| Spec | OpenAPI 3.x | Codegen for Go (vf-agents), TS (UIs), auto-documentation |
| Versioning | URL-based (`/v1/`) | Simple, visible, easy to route |
| Events | SSE | One-way, auto-reconnect, works through proxies |
| Pagination | Cursor-based | Better than offset for real-time data where items move |
| Auth | Bearer token (see gap #8) | Simple, works for all consumers |
| Content-Type | `application/json` | All requests and responses |

Alternatives considered:
- JSON-RPC — natural for actions but less tooling and convention
- gRPC — overkill for browser, needs proxy
- tRPC — locks out Go consumers (vf-agents)
- WebSocket — unnecessary complexity since events are server→client only

## Endpoints

### System

```
GET  /v1/health                          Liveness (DB connection, etc.)
GET  /v1/status                          System stats: active initiatives, task counts,
                                         registered agents, event stream subscribers
```

### Initiatives

```
POST   /v1/initiatives                   Create initiative
GET    /v1/initiatives                   List (filter: status, tags, search)
GET    /v1/initiatives/:id               Get details
PATCH  /v1/initiatives/:id               Update fields
POST   /v1/initiatives/:id/archive       Archive initiative
POST   /v1/initiatives/:id/complete      Complete initiative
GET    /v1/initiatives/:id/stats         Aggregate stats (task counts by status, progress %)
```

### Phases

```
POST   /v1/initiatives/:id/phases        Create phase in initiative
GET    /v1/initiatives/:id/phases         List phases in initiative
GET    /v1/phases/:id                     Get phase details
PATCH  /v1/phases/:id                     Update fields
POST   /v1/phases/:id/activate            Activate manually
POST   /v1/phases/:id/complete            Complete manually
GET    /v1/phases/:id/stats               Aggregate stats
```

### Tasks

```
POST   /v1/phases/:id/tasks              Create task in phase
GET    /v1/tasks                          List/search tasks
GET    /v1/tasks/:id                      Get details (?expand=links,reviews,events)
PATCH  /v1/tasks/:id                      Update fields
```

**Task list filters:**
- `?status=doing,blocked` — multiple statuses
- `?phase=id` — tasks in a phase
- `?initiative=id` — tasks in an initiative
- `?assigned_to=agent-id` — pinned to agent
- `?requires=opus,architect` — matching required tags
- `?claimable=true&tags=x,y` — claimable by agent with given tags
- `?search=keyword` — full-text search on title and description
- `?sort=created_at|updated_at|claimed_at` — sort order
- `?cursor=x&limit=50` — pagination

### Task Lifecycle Actions

Each action validates against the state machine. Invalid transitions return `INVALID_TRANSITION` error.

```
POST   /v1/tasks/:id/submit              Draft → pending_start_review or todo
POST   /v1/tasks/:id/claim               Claim task (atomic, tag-matched)
POST   /v1/tasks/:id/unclaim             Release without failure → todo
POST   /v1/tasks/:id/complete            Mark done (body: commit/MR refs)
POST   /v1/tasks/:id/fail                Agent gave up → needs_attention (body: reason)
POST   /v1/tasks/:id/resubmit            changes_requested → review_return_to gate
POST   /v1/tasks/:id/block               Block (body: reason, optional external_ref)
POST   /v1/tasks/:id/unblock             Unblock → todo or doing
POST   /v1/tasks/:id/defer               Defer from any non-terminal state
POST   /v1/tasks/:id/cancel              Cancel from any non-terminal state
POST   /v1/tasks/:id/assign              Pin to specific agent (body: agent_id)
POST   /v1/tasks/:id/unassign            Remove agent pin
POST   /v1/tasks/:id/heartbeat           Extend claim timeout
POST   /v1/tasks/:id/progress            Report progress (body: message)
```

**Convenience:**
```
GET    /v1/tasks/claimable               Tasks claimable by agent (?tags=x,y)
                                         Returns todo, not dependency-blocked, tag-matched
```

### Notes

Append-only comments on tasks by any actor. Different from reviews (which are formal approve/reject decisions).

```
POST   /v1/tasks/:id/notes               Add a note (body: text, actor_id)
GET    /v1/tasks/:id/notes               List notes for task
```

### Reviews

Formal review decisions at review gates.

```
POST   /v1/tasks/:id/reviews             Submit review (body: decision, reason)
GET    /v1/tasks/:id/reviews             List reviews for task
```

Review body:
```json
{
  "decision": "approved | rejected | changes_requested",
  "reason": "Missing test for edge case",
  "reviewer_id": "human-jason",
  "reviewer_type": "human | agent"
}
```

### Links

Universal link system — source can be initiative, phase, or task.

```
POST   /v1/links                         Create link (body: source_id, target_id, link_type)
DELETE /v1/links/:id                      Remove link
GET    /v1/links                          List links (?source=id OR ?target=id OR ?type=x)
```

### Task Events (Read-Only)

Append-only audit log of everything that happened to a task.

```
GET    /v1/tasks/:id/events              Event timeline for a task
GET    /v1/events                        Query events across tasks
                                         (?initiative=id, ?agent=id, ?type=x, ?since=timestamp)
```

### Event Stream (SSE)

Real-time server-sent events for live updates.

```
GET    /v1/events/stream                 SSE endpoint
                                         (?initiative=id, ?phase=id, ?type=x)
```

**SSE event format:**
```
id: evt_abc123
event: task.status_changed
data: {"task_id": "xyz", "from": "todo", "to": "doing", "agent_id": "agent-7", "timestamp": "..."}
```

**Reconnection:** Supports `Last-Event-ID` header. On reconnect, replays all events after the given ID. Retention window: 24 hours.

**Event types emitted on the stream:**
```
task.created
task.updated
task.status_changed
task.claimed
task.unclaimed
task.completed
task.failed
task.blocked
task.unblocked
task.heartbeat

review.submitted

link.added
link.removed

initiative.created
initiative.updated
initiative.completed
initiative.archived

phase.created
phase.updated
phase.activated
phase.completed

agent.registered
agent.deregistered
agent.status_changed
```

### Agents

Agent registration and status tracking.

```
POST   /v1/agents/register               Register agent (body: name, tags)
GET    /v1/agents                         List agents (?status=online,busy)
GET    /v1/agents/:id                     Get agent details
PATCH  /v1/agents/:id                     Update tags, status
DELETE /v1/agents/:id                     Deregister
GET    /v1/agents/:id/tasks               Tasks currently claimed by this agent
```

Agent shape:
```json
{
  "id": "agent-claude-7",
  "name": "Claude Opus Worker 7",
  "tags": ["executor", "opus", "high-reasoning"],
  "status": "online | offline | busy",
  "registered_at": "2026-03-19T14:00:00Z",
  "last_heartbeat": "2026-03-19T14:30:00Z"
}
```

### Bulk Operations

For intake tooling — create an entire initiative structure in one call.

```
POST   /v1/bulk/import                    Create initiative + phases + tasks + links
```

Request body:
```json
{
  "initiative": {
    "name": "Auth rewrite",
    "description": "...",
    "tags": ["backend"]
  },
  "phases": [
    {
      "ref": "phase-1",
      "name": "Core auth",
      "tasks": [
        {
          "ref": "task-1",
          "title": "Implement JWT validation",
          "description": "...",
          "acceptance_criteria": ["..."],
          "requires": ["executor"]
        }
      ]
    }
  ],
  "links": [
    { "source_ref": "task-1", "target_ref": "phase-1", "type": "depends_on" }
  ]
}
```

Uses temporary `ref` fields for internal cross-referencing. Returns mapping of refs to created nanoid IDs.

## Agent Liveness & Claim Timeout

Critical safety mechanism: prevents tasks from being stuck in `doing` when an agent dies.

### How it works

1. Tasks have a `claim_timeout` (default configurable at phase/initiative level, e.g., 30 minutes)
2. When a task is claimed, `claim_expires_at` is set to `now + claim_timeout`
3. Agent extends the timeout by calling `POST /tasks/:id/heartbeat`
4. A background process in the API server periodically checks for expired claims
5. Expired claim → task moves to `needs_attention` with reason "agent unresponsive (claim expired)"

### Task fields

```
claim_timeout: duration (default: 30m, configurable per phase/initiative)
claim_expires_at: ISO 8601 | null (set on claim, extended on heartbeat)
claimed_by: agent_id | null
claimed_at: ISO 8601 | null
```

### Background process

Runs every 60 seconds:
```sql
UPDATE tasks
SET status = 'needs_attention',
    claimed_by = NULL,
    claim_expires_at = NULL
WHERE status = 'doing'
  AND claim_expires_at < NOW()
```

Records a `task_event` with type `claim_expired` for each affected task.

## Cross-Cutting Concerns

### Pagination

Cursor-based on all list endpoints:
```
GET /v1/tasks?cursor=eyJpZCI6ImFiYyJ9&limit=50
```

Response includes:
```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJpZCI6ImRlZiJ9",
    "has_more": true
  }
}
```

### Error Model

Consistent across all endpoints:
```json
{
  "error": {
    "code": "INVALID_TRANSITION",
    "message": "Cannot transition from 'done' to 'doing'",
    "details": {
      "current_status": "done",
      "requested_status": "doing",
      "valid_transitions": []
    }
  }
}
```

Standard error codes:

| Code | HTTP Status | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Invalid request body/parameters |
| `UNAUTHORIZED` | 401 | Missing or invalid auth token |
| `FORBIDDEN` | 403 | Valid auth but insufficient permissions |
| `NOT_FOUND` | 404 | Entity not found |
| `CONFLICT` | 409 | Concurrent modification (e.g., already claimed) |
| `INVALID_TRANSITION` | 422 | State machine violation |
| `ALREADY_CLAIMED` | 409 | Task already claimed by another agent |
| `CLAIM_EXPIRED` | 410 | Claim timeout expired |
| `DEPENDENCY_UNMET` | 422 | Task has unresolved depends_on links |

### Idempotency

All POST operations support `Idempotency-Key` header:
```
POST /v1/tasks/abc123/claim
Idempotency-Key: req-xyz-789
```

If the same key is sent again, the server returns the original response without re-executing. Keys are retained for 24 hours.

Critical for agent operations — network failures during claim/complete shouldn't cause duplicates or errors.

### CORS

Required for Web UI SPA. Allow configured origins, standard headers, and SSE.

### Rate Limiting

Not v1. Design the API so rate limiting can be added at the reverse proxy layer without API changes.

## Future Considerations

- **Webhooks**: For external systems (CI, Jira, Slack) that can't maintain SSE connections. The events table already supports this — webhooks are just another event consumer.
- **GraphQL**: If the expand/filter needs get complex, a GraphQL layer on top of the REST API could reduce round trips. Not v1.
- **gRPC**: For high-frequency agent-to-API communication if REST overhead becomes measurable. Not v1.
