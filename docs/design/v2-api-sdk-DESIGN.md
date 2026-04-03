# v2 API + SDK — Design Specification

**Date:** 2026-04-03
**Status:** Draft
**Prerequisite:** [entity-display-names-ANALYSIS.md](../entity-display-names-ANALYSIS.md)

## Overview

This document specifies the concrete contracts for three components designed as one system:

1. **v2 REST API** — Django/DRF endpoints returning embedded entity summaries
2. **vtf-sdk-python** — Typed Python client (sync + async) for CLI, vafi, vtf-kb
3. **vtf-sdk-ts** — Typed TypeScript client + React hooks for the web SPA

The analysis doc contains the reasoning, trade-offs, and architectural decisions. This document contains the **contracts** — what each layer looks like, exactly.

Design flows backwards from consumer experience to API shape to database query:

```
SDK consumer writes:     task.project.name
SDK type requires:       Task.project: ProjectRef
API must return:         {"project": {"id": "...", "name": "..."}}
Serializer produces:     to_representation() with select_related('project')
Database stores:         tasks.project_id FK → projects.id
```

---

## 1. Shared Type Contracts

These types are the single source of truth. They appear identically (modulo language syntax) in the v2 API JSON, the Python SDK, and the TypeScript SDK.

### 1.1 Entity Reference Types

Every FK or string-ID reference in a v2 response is one of these shapes. Never a bare ID.

#### ProjectRef

```json
{"id": "xY9kLm2Nq_pRs3tUvWz", "name": "Auth System"}
```

```python
@dataclass(frozen=True)
class ProjectRef:
    id: str
    name: str
```

```typescript
interface ProjectRef {
  readonly id: string;
  readonly name: string;
}
```

**Appears in:** Task.project, Workplan.project, Membership.project, Lock.project, ChannelMapping.project

---

#### WorkplanRef

```json
{"id": "aBcDeFgHiJkLmNoPqRs", "name": "Platform Hardening"}
```

```python
@dataclass(frozen=True)
class WorkplanRef:
    id: str
    name: str
```

```typescript
interface WorkplanRef {
  readonly id: string;
  readonly name: string;
}
```

**Appears in:** Task.workplan, Milestone.workplan

---

#### MilestoneRef

```json
{"id": "zZzYyYxXwWvVuUtTsSr", "name": "Phase 1 Core", "status": "active"}
```

```python
@dataclass(frozen=True)
class MilestoneRef:
    id: str
    name: str
    status: str  # "pending" | "active" | "completed"
```

```typescript
interface MilestoneRef {
  readonly id: string;
  readonly name: string;
  readonly status: 'pending' | 'active' | 'completed';
}
```

**Appears in:** Task.milestone

**Why status is included:** Milestone status is frequently needed for display (badge color, filtering). Including it avoids a follow-up call for the most common use case.

---

#### TaskRef

```json
{"id": "tsk-abc-123", "title": "Add auth endpoint", "status": "doing"}
```

```python
@dataclass(frozen=True)
class TaskRef:
    id: str
    title: str
    status: str
```

```typescript
interface TaskRef {
  readonly id: string;
  readonly title: string;
  readonly status: TaskStatus;
}
```

**Appears in:** Task.requires, Link.source (when type=task), Link.target (when type=task), Agent.current_task

**Note:** Tasks use `title` not `name`. The SDK's `EntityRef` base provides a `.display_name` property that returns `title` for TaskRef and `name` for all others.

---

#### AgentRef

```json
{"id": "agt-executor-001", "name": "executor-1"}
```

```python
@dataclass(frozen=True)
class AgentRef:
    id: str
    name: str
```

```typescript
interface AgentRef {
  readonly id: string;
  readonly name: string;
}
```

**Appears in:** Task.claimed_by, Task.assigned_to, Review.reviewer, Note.actor, TaskEvent.triggered_by

**Resolution:** `claimed_by`, `assigned_to`, etc. are CharField on the model (not FK). The v2 serializer resolves them via batch lookup against the Agent table, falling back to User table, falling back to degraded ref `{"id": "original-value", "name": "original-value"}`.

---

#### UserRef

```json
{"id": "42", "username": "jdoe"}
```

```python
@dataclass(frozen=True)
class UserRef:
    id: str
    username: str
```

```typescript
interface UserRef {
  readonly id: string;
  readonly username: string;
}
```

**Appears in:** Project.owner, Project.created_by, Workplan.owner, Workplan.created_by, Milestone.created_by, Membership.user

**Note:** UserRef uses `username` not `name`, following Django's User model convention.

---

#### ActorRef (union of AgentRef | UserRef)

Some fields can reference either an agent or a user. The v2 response includes a `type` discriminator:

```json
// Agent actor
{"type": "agent", "id": "agt-001", "name": "executor-1"}

// User actor
{"type": "user", "id": "42", "username": "jdoe"}
```

```python
@dataclass(frozen=True)
class ActorRef:
    type: str  # "agent" | "user"
    id: str
    display_name: str  # name for agents, username for users

    @classmethod
    def from_dict(cls, data: dict) -> 'ActorRef':
        return cls(
            type=data["type"],
            id=data["id"],
            display_name=data.get("name") or data.get("username") or data["id"],
        )
```

```typescript
type ActorRef =
  | { readonly type: 'agent'; readonly id: string; readonly name: string }
  | { readonly type: 'user'; readonly id: string; readonly username: string };
```

**Appears in:** Task.claimed_by, Task.assigned_to, Task.created_by, Review.reviewer, Note.actor, TaskEvent.triggered_by

**Rationale for ActorRef over separate AgentRef/UserRef:** These fields can hold either type. Without a discriminator, the SDK would need to guess based on ID format (fragile). The `type` field makes it explicit.

---

#### LinkRef (polymorphic — internal or external)

```json
// Internal entity reference
{"type": "task", "id": "tsk-abc", "title": "Add auth", "status": "doing"}
{"type": "milestone", "id": "ms-xyz", "name": "Phase 1", "status": "active"}
{"type": "workplan", "id": "wp-123", "name": "Platform Hardening"}

// External reference
{"type": "jira", "id": "PROJ-1234", "label": "PROJ-1234"}
{"type": "commit", "id": "abc123def", "label": "abc123d"}
```

```python
@dataclass(frozen=True)
class InternalLinkRef:
    type: str             # "task" | "milestone" | "workplan"
    id: str
    display_name: str     # title for tasks, name for others
    status: str | None    # present for tasks and milestones

@dataclass(frozen=True)
class ExternalLinkRef:
    type: str             # "commit" | "jira" | "doc" | "file" | "area"
    id: str
    label: str            # human-readable display text

LinkRef = InternalLinkRef | ExternalLinkRef
```

```typescript
type InternalLinkRef =
  | { readonly type: 'task'; readonly id: string; readonly title: string; readonly status: TaskStatus }
  | { readonly type: 'milestone'; readonly id: string; readonly name: string; readonly status: MilestoneStatus }
  | { readonly type: 'workplan'; readonly id: string; readonly name: string };

type ExternalLinkRef = {
  readonly type: 'commit' | 'jira' | 'doc' | 'file' | 'area';
  readonly id: string;
  readonly label: string;
};

type LinkRef = InternalLinkRef | ExternalLinkRef;
```

**Appears in:** Link.source (InternalLinkRef only), Link.target (any LinkRef)

---

### 1.2 Permissions Object

Every v2 entity response includes a `_permissions` object describing what the authenticated user can do:

```json
{
  "id": "tsk-abc",
  "title": "Add auth endpoint",
  "status": "todo",
  "_permissions": {
    "can_edit": true,
    "can_delete": false,
    "available_actions": ["claim", "block", "defer", "cancel"]
  }
}
```

The shape varies by entity type:

#### Task Permissions

```json
{
  "can_edit": true,
  "can_delete": false,
  "available_actions": ["claim", "block", "defer", "cancel"]
}
```

`available_actions` is computed from the state machine — only valid transitions for the current status AND the current user's role.

#### Project Permissions

```json
{
  "can_edit": true,
  "can_delete": false,
  "can_archive": true,
  "can_manage_members": true
}
```

#### Workplan / Milestone Permissions

```json
{
  "can_edit": true,
  "can_delete": false,
  "can_archive": true,
  "can_complete": true
}
```

---

### 1.3 Null Contract

- Nullable references are JSON `null`, never absent, never empty objects
- Every field is always present in the response
- `null` means "not set"

```json
{
  "project": {"id": "...", "name": "..."},
  "workplan": null,
  "milestone": null,
  "claimed_by": null
}
```

### 1.4 Error Contract

All v2 errors use one format:

```json
{
  "error": {
    "code": "GUARD_VIOLATION",
    "message": "Task must belong to a workplan before submission",
    "details": {
      "guard": "guard_has_workplan",
      "task_id": "tsk-abc",
      "current_status": "draft"
    },
    "field_errors": null
  }
}
```

For validation errors:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "details": null,
    "field_errors": {
      "title": ["This field may not be blank."],
      "project": ["This field is required."]
    }
  }
}
```

#### Error Code Taxonomy

| HTTP Status | Error Code | SDK Exception | When |
|-------------|-----------|---------------|------|
| 400 | `VALIDATION_ERROR` | `ValidationError` | Invalid field values |
| 400 | `BAD_REQUEST` | `BadRequest` | Malformed request |
| 401 | `AUTHENTICATION_REQUIRED` | `AuthenticationRequired` | No/invalid token |
| 403 | `PERMISSION_DENIED` | `PermissionDenied` | Insufficient role/membership |
| 404 | `NOT_FOUND` | `NotFound` / `TaskNotFound` / etc. | Resource doesn't exist |
| 405 | `METHOD_NOT_ALLOWED` | `MethodNotAllowed` | Wrong HTTP verb |
| 409 | `CONFLICT` | `Conflict` | Generic conflict |
| 409 | `ALREADY_CLAIMED` | `ClaimConflict` | Task claimed by another agent |
| 409 | `GUARD_VIOLATION` | `GuardViolation` | State machine guard failed |
| 409 | `DUPLICATE` | `DuplicateError` | Duplicate membership, lock, etc. |
| 422 | `INVALID_TRANSITION` | `InvalidTransition` | Invalid state machine transition |
| 429 | `RATE_LIMITED` | `RateLimited` | Too many requests |
| 503 | `SERVICE_UNAVAILABLE` | `ServiceUnavailable` | Database/Redis down |

---

## 2. v2 API Specification

### 2.1 Versioning

- Mechanism: URL prefix `/v2/`
- DRF `URLPathVersioning` sets `request.version`
- Same viewsets serve both `/v1/` and `/v2/` via `VersionedSerializerMixin`
- v1 serializers unchanged, v2 serializers are separate classes

### 2.2 OpenAPI Specification (Stripe Approach)

The OpenAPI spec serves as **documentation and CI validation**, not as the source of truth. The v2 serializers are the source of truth; the spec is derived from them.

**Tooling:** `drf-spectacular` generates the OpenAPI 3.0 spec from DRF serializers and views.

**Published at:**
- `GET /v2/schema/` — OpenAPI 3.0 JSON schema
- `GET /v2/schema/swagger-ui/` — Interactive Swagger UI documentation
- `GET /v2/schema/redoc/` — Redoc documentation

**How it fits in the architecture:**

```
v2 Serializers (source of truth)
    │
    ├──→ REST API responses (runtime)
    ├──→ MCP tool responses (via shared serializer, runtime)
    ├──→ OpenAPI spec (generated by drf-spectacular, build-time)
    │       │
    │       ├──→ Swagger UI / Redoc (documentation)
    │       ├──→ SDK alignment tests (CI validation)
    │       └──→ External consumers (machine-readable contract)
    │
    └──→ Hand-written SDKs (ergonomic developer experience)
            │
            └──→ CI tests verify SDK types match OpenAPI schema
```

**CI validation rule:** A test in each SDK verifies that every entity type's fields match the corresponding OpenAPI schema component. If the API adds or removes a field and the SDK doesn't update, CI fails.

```python
# vtf-sdk-python CI test
def test_task_fields_match_openapi():
    spec = fetch_openapi_spec("/v2/schema/")
    api_fields = set(spec["components"]["schemas"]["Task"]["properties"].keys())
    sdk_fields = set(f.name for f in fields(Task))
    # Remove SDK-only fields (permissions, internal)
    sdk_fields -= {"permissions"}
    assert api_fields == sdk_fields, f"Drift: {api_fields.symmetric_difference(sdk_fields)}"
```

```typescript
// @vtf/sdk CI test
test('Task type matches OpenAPI schema', async () => {
  const spec = await fetch('/v2/schema/').then(r => r.json());
  const apiFields = Object.keys(spec.components.schemas.Task.properties);
  const sdkFields = Object.keys(taskFieldMap);  // maintained list
  expect(new Set(apiFields)).toEqual(new Set(sdkFields));
});
```

**Why not contract-first (spec → code generation)?**

Contract-first would generate SDKs from the spec automatically. But generated SDKs produce flat function calls, not the resource-oriented `task.project.name` experience with lazy loading, managers, and domain exceptions. We'd hand-write the SDKs on top of generated ones, adding a layer without benefit.

The Stripe pattern — hand-crafted SDKs validated against a generated spec — gives the best of both: ergonomic developer experience AND contract-enforced consistency.

### 2.3 Global Conventions

| Convention | v2 Rule |
|-----------|---------|
| **List responses** | Always paginated: `{"results": [...], "next": "cursor", "previous": null}` |
| **Single entity** | Direct object (no envelope), includes `_permissions` |
| **Errors** | Always `{"error": {"code": "...", "message": "...", "details": ..., "field_errors": ...}}` |
| **Null fields** | Always present, JSON `null` for unset |
| **Field naming** | `snake_case` throughout |
| **Dates** | ISO 8601 with UTC: `2026-04-03T12:30:45.123456Z` |
| **Pagination** | Cursor-based, `page_size` param, default 50, max 100 |
| **Filter params** | Always suffixed: `project_id`, `workplan_id`, `milestone_id`, `task_id` |
| **201 responses** | Include `Location` header |
| **Idempotency** | `Idempotency-Key` header honored on all POST mutations |
| **Content type** | JSON only (`application/json`) |

### 2.3 Entity Response Shapes

#### Task (v2)

`GET /v2/tasks/{id}/`

```json
{
  "id": "tsk-abc-123",
  "title": "Add auth endpoint",
  "description": "Implement token validation...",
  "status": "doing",
  "project": {"id": "xY9...", "name": "Auth System"},
  "workplan": {"id": "aBc...", "name": "Platform Hardening"},
  "milestone": {"id": "zZz...", "name": "Phase 1 Core", "status": "active"},
  "labels": ["backend", "security"],
  "acceptance_criteria": ["Token validated", "Tests pass"],
  "needs_review_before_start": false,
  "needs_review_on_completion": true,
  "review_return_to": null,
  "requires": [
    {"id": "tsk-def-456", "title": "Create user model", "status": "done"},
    {"id": "tsk-ghi-789", "title": "Add login endpoint", "status": "doing"}
  ],
  "assigned_to": {"type": "agent", "id": "agt-001", "name": "executor-1"},
  "claimed_by": {"type": "agent", "id": "agt-001", "name": "executor-1"},
  "claimed_at": "2026-04-03T10:00:00Z",
  "claim_timeout": "PT30M",
  "claim_expires_at": "2026-04-03T10:30:00Z",
  "created_by": {"type": "user", "id": "42", "username": "jdoe"},
  "spec": "...",
  "agent_model": "sonnet",
  "test_command": {"unit": "pytest tests/"},
  "judge": true,
  "isolation": "worktree",
  "retry_count": 0,
  "execution_summary": null,
  "created_at": "2026-04-03T09:00:00Z",
  "updated_at": "2026-04-03T10:00:00Z",
  "_permissions": {
    "can_edit": true,
    "can_delete": false,
    "available_actions": ["complete", "fail", "block"]
  }
}
```

**Write (POST/PATCH):** Accepts bare IDs for all reference fields:

```json
{
  "title": "Add auth endpoint",
  "project": "xY9...",
  "workplan": "aBc...",
  "milestone": "zZz...",
  "assigned_to": "agt-001"
}
```

**Expand support:** `?expand=links,reviews,events,traces` — same as v1.

---

#### Project (v2)

`GET /v2/projects/{id}/`

```json
{
  "id": "xY9kLm2Nq_pRs3tUvWz",
  "name": "Auth System",
  "description": "Authentication and authorization service",
  "status": "active",
  "repo_url": "https://github.com/vilosource/auth-system",
  "default_branch": "main",
  "tags": ["backend", "security"],
  "owner": {"type": "user", "id": "42", "username": "jdoe"},
  "created_by": {"type": "user", "id": "42", "username": "jdoe"},
  "created_at": "2026-03-01T00:00:00Z",
  "updated_at": "2026-04-03T10:00:00Z",
  "_permissions": {
    "can_edit": true,
    "can_delete": false,
    "can_archive": true,
    "can_manage_members": true
  }
}
```

---

#### Workplan (v2)

`GET /v2/workplans/{id}/`

```json
{
  "id": "aBcDeFgHiJkLmNoPqRs",
  "name": "Platform Hardening",
  "description": "Security and reliability improvements",
  "status": "active",
  "project": {"id": "xY9...", "name": "Auth System"},
  "owner": {"type": "user", "id": "42", "username": "jdoe"},
  "tags": ["hardening"],
  "target_date": "2026-06-01T00:00:00Z",
  "default_needs_review_before_start": false,
  "default_needs_review_on_completion": true,
  "created_by": {"type": "user", "id": "42", "username": "jdoe"},
  "created_at": "2026-03-15T00:00:00Z",
  "updated_at": "2026-04-03T10:00:00Z",
  "_permissions": {
    "can_edit": true,
    "can_delete": false,
    "can_archive": true,
    "can_complete": true
  }
}
```

---

#### Milestone (v2)

`GET /v2/milestones/{id}/`

```json
{
  "id": "zZzYyYxXwWvVuUtTsSr",
  "name": "Phase 1 Core",
  "description": "Core filtering and query paths",
  "status": "active",
  "order": 1,
  "workplan": {"id": "aBc...", "name": "Platform Hardening"},
  "default_needs_review_before_start": null,
  "default_needs_review_on_completion": null,
  "created_by": {"type": "user", "id": "42", "username": "jdoe"},
  "created_at": "2026-03-15T00:00:00Z",
  "updated_at": "2026-04-03T10:00:00Z",
  "_permissions": {
    "can_edit": true,
    "can_delete": false,
    "can_activate": true,
    "can_complete": false
  }
}
```

---

#### Agent (v2)

`GET /v2/agents/{id}/`

```json
{
  "id": "agt-executor-001",
  "name": "executor-1",
  "tags": ["executor", "sonnet"],
  "status": "online",
  "effective_status": "online",
  "last_heartbeat": "2026-04-03T10:29:00Z",
  "pod_name": "vafi-executor-7f8b9c-abc",
  "registered_at": "2026-04-01T00:00:00Z",
  "current_task": {"id": "tsk-abc", "title": "Add auth endpoint", "status": "doing"},
  "tasks_completed": 14,
  "tasks_failed": 1,
  "created_at": "2026-04-01T00:00:00Z",
  "updated_at": "2026-04-03T10:29:00Z"
}
```

**Note:** Agent already uses the TaskRef pattern for `current_task` in v1. v2 preserves this.

---

#### Review (v2)

`GET /v2/tasks/{id}/reviews/`

```json
{
  "results": [
    {
      "id": "rev-abc-123",
      "task": {"id": "tsk-abc", "title": "Add auth endpoint", "status": "pending_completion_review"},
      "decision": "changes_requested",
      "reason": "Missing error handling for invalid tokens",
      "reviewer": {"type": "agent", "id": "agt-judge-001", "name": "judge-1"},
      "reviewer_type": "agent",
      "created_at": "2026-04-03T11:00:00Z",
      "updated_at": "2026-04-03T11:00:00Z"
    }
  ],
  "next": null,
  "previous": null
}
```

**Change from v1:** `reviewer_id` (bare string) → `reviewer` (ActorRef object). `task` (bare ID) → `task` (TaskRef object).

---

#### Note (v2)

```json
{
  "id": "note-abc-123",
  "task": {"id": "tsk-abc", "title": "Add auth endpoint", "status": "doing"},
  "text": "All tests passing, ready for review",
  "actor": {"type": "agent", "id": "agt-001", "name": "executor-1"},
  "created_at": "2026-04-03T11:30:00Z"
}
```

**Change from v1:** `actor_id` (bare string) → `actor` (ActorRef object).

---

#### Link (v2)

```json
{
  "id": "lnk-abc-123",
  "source": {"type": "task", "id": "tsk-abc", "title": "Add auth", "status": "doing"},
  "target": {"type": "task", "id": "tsk-def", "title": "Create user model", "status": "done"},
  "link_type": "depends_on",
  "metadata": null,
  "created_by": {"type": "user", "id": "42", "username": "jdoe"},
  "created_at": "2026-04-03T09:00:00Z",
  "updated_at": "2026-04-03T09:00:00Z"
}
```

**Change from v1:** `source_type` + `source_id` + `source_title` → `source` (InternalLinkRef). `target_type` + `target_id` + `target_title` → `target` (LinkRef). Eliminates the N+1 per-row lookup.

---

#### TaskEvent (v2)

```json
{
  "id": "evt-abc-123",
  "task": {"id": "tsk-abc", "title": "Add auth endpoint", "status": "doing"},
  "event_type": "claimed",
  "data": {"agent_id": "agt-001"},
  "triggered_by": {"type": "agent", "id": "agt-001", "name": "executor-1"},
  "timestamp": "2026-04-03T10:00:00Z"
}
```

**Change from v1:** `task` (bare ID) → TaskRef. `triggered_by` (bare string) → ActorRef.

---

#### Token Validation (v2)

`GET /v2/auth/validate/`

```json
{
  "user_id": 42,
  "username": "jdoe",
  "user_type": "human",
  "is_staff": false,
  "projects": [
    {
      "project": {"id": "xY9...", "name": "Auth System"},
      "role": "owner"
    }
  ]
}
```

**Change from v1:** `project_id` (bare string) → `project` (ProjectRef).

---

### 2.4 SSE Event Payload (v2)

Events enriched with display data:

```json
{
  "id": "evt-abc-123",
  "event": "task.status_changed",
  "data": {
    "task_id": "tsk-abc",
    "task_title": "Add auth endpoint",
    "from_status": "todo",
    "to_status": "doing",
    "actor": {"type": "agent", "id": "agt-001", "name": "executor-1"}
  }
}
```

---

## 3. Python SDK Specification

### 3.1 Package Structure

```
vtf-sdk-python/
  vtf_sdk/
    __init__.py           # VtfClient, AsyncVtfClient
    client.py             # Client implementations
    entities.py           # Task, Project, Workplan, Milestone, Agent, etc.
    refs.py               # ProjectRef, WorkplanRef, MilestoneRef, TaskRef, ActorRef, LinkRef
    managers.py           # TaskManager, ProjectManager, etc.
    exceptions.py         # Domain exception hierarchy
    auth.py               # TokenAuth, OAuthAuth, auth strategies
    pagination.py         # PagedResult, lazy iterator
    protocols.py          # VtfClientProtocol, manager protocols
    testing/
      __init__.py         # MockVtfClient, factories
      mock_client.py      # In-memory client implementation
      factories.py        # build_task, build_project, etc.
```

### 3.2 Client

```python
from vtf_sdk import VtfClient, AsyncVtfClient

# Sync
vtf = VtfClient(url="https://vtf.example.com", token="...")
vtf = VtfClient(url="...", auth=TokenAuth("..."))  # explicit auth strategy

# Async
vtf = AsyncVtfClient(url="...", token="...")

# Managers
vtf.projects    # ProjectManager
vtf.workplans   # WorkplanManager
vtf.milestones  # MilestoneManager
vtf.tasks       # TaskManager
vtf.agents      # AgentManager
vtf.links       # LinkManager
vtf.bulk        # BulkManager
```

### 3.3 Entity Types

All entities are frozen dataclasses (immutable). Mutations return new instances.

```python
@dataclass(frozen=True)
class Task:
    id: str
    title: str
    description: str
    status: str
    project: ProjectRef
    workplan: WorkplanRef | None
    milestone: MilestoneRef | None
    labels: list[str]
    acceptance_criteria: list[str]
    needs_review_before_start: bool | None
    needs_review_on_completion: bool | None
    review_return_to: str | None
    requires: list[TaskRef]
    assigned_to: ActorRef | None
    claimed_by: ActorRef | None
    claimed_at: datetime | None
    claim_timeout: timedelta | None
    claim_expires_at: datetime | None
    created_by: ActorRef | None
    spec: str
    agent_model: str
    test_command: dict
    judge: bool
    isolation: str
    retry_count: int
    execution_summary: dict | None
    permissions: TaskPermissions
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str:
        return self.title
```

### 3.4 Manager API

```python
class TaskManager:
    # Read
    def get(self, id: str, expand: list[str] | None = None) -> Task: ...
    def list(self, *, status: str = None, project_id: str = None,
             workplan_id: str = None, milestone_id: str = None,
             page: int = 1, per_page: int = 50) -> PagedResult[Task]: ...
    def list_all(self, **filters) -> Iterator[Task]: ...
    def claimable(self, *, tags: list[str] = None, project_id: str = None) -> PagedResult[Task]: ...

    # State transitions (return updated Task)
    def submit(self, id: str) -> Task: ...
    def claim(self, id: str, *, agent_id: str) -> Task: ...
    def unclaim(self, id: str) -> Task: ...
    def complete(self, id: str) -> Task: ...
    def fail(self, id: str) -> Task: ...
    def recover(self, id: str, *, target: str) -> Task: ...
    def resubmit(self, id: str) -> Task: ...
    def block(self, id: str, *, reason: str = "") -> Task: ...
    def unblock(self, id: str) -> Task: ...
    def defer(self, id: str) -> Task: ...
    def cancel(self, id: str) -> Task: ...
    def heartbeat(self, id: str) -> None: ...
    def assign(self, id: str, *, agent_id: str) -> Task: ...
    def unassign(self, id: str) -> Task: ...

    # Write
    def create(self, *, title: str, project: str | ProjectRef,
               workplan: str | WorkplanRef | None = None,
               milestone: str | MilestoneRef | None = None,
               **kwargs) -> Task: ...
    def update(self, id: str, **kwargs) -> Task: ...
    def delete(self, id: str) -> None: ...

    # Notes (nested)
    def list_notes(self, task_id: str) -> PagedResult[Note]: ...
    def add_note(self, task_id: str, *, text: str, actor_id: str = "") -> Note: ...

    # Reviews (nested)
    def list_reviews(self, task_id: str) -> PagedResult[Review]: ...
    def submit_review(self, task_id: str, *, decision: str, reason: str,
                      reviewer_id: str, reviewer_type: str = "agent") -> Review: ...
```

### 3.5 Pagination

```python
@dataclass(frozen=True)
class PagedResult(Generic[T]):
    items: list[T]
    has_more: bool
    next_cursor: str | None
    previous_cursor: str | None
```

### 3.6 Exception Hierarchy

```python
class VtfError(Exception):
    """Base for all SDK exceptions."""
    code: str
    message: str
    details: dict | None

class AuthenticationRequired(VtfError): ...
class PermissionDenied(VtfError): ...
class NotFound(VtfError): ...
class TaskNotFound(NotFound): ...
class ProjectNotFound(NotFound): ...
class ValidationError(VtfError):
    field_errors: dict[str, list[str]]
class Conflict(VtfError): ...
class ClaimConflict(Conflict):
    held_by: str  # who holds the claim
class GuardViolation(Conflict):
    guard_name: str
class InvalidTransition(VtfError):
    current_status: str
    attempted_action: str
class DuplicateError(Conflict): ...
class RateLimited(VtfError): ...
class ServiceUnavailable(VtfError): ...
```

---

## 4. TypeScript SDK Specification

### 4.1 Package Structure

```
@vtf/sdk/
  src/
    index.ts              # VtfClient
    client.ts             # Client implementation
    entities.ts           # Task, Project, Workplan, etc.
    refs.ts               # ProjectRef, WorkplanRef, etc.
    managers.ts           # TaskManager, ProjectManager, etc.
    exceptions.ts         # Error class hierarchy
    auth.ts               # Auth strategies
    pagination.ts         # PagedResult
    types.ts              # TaskStatus, MilestoneStatus, etc.
  testing/
    index.ts              # createMockClient, factories
    mock-client.ts
    factories.ts

@vtf/sdk-react/
  src/
    index.ts              # hooks
    hooks/
      useTask.ts
      useTasks.ts
      useProject.ts
      useWorkplan.ts
      useMilestone.ts
      useAgents.ts
      useVtfEvents.ts     # SSE → React Query cache bridge
    mutations/
      useClaimTask.ts
      useSubmitTask.ts
      useCompleteTask.ts
      ...
    provider.ts           # VtfProvider (React context)
```

### 4.2 Client

```typescript
import { VtfClient } from '@vtf/sdk';

const vtf = new VtfClient({
  baseUrl: 'https://vtf.example.com',
  token: '...',
  // or: credentials: 'include' (for session auth in browser)
});

vtf.projects    // ProjectManager
vtf.tasks       // TaskManager
vtf.workplans   // WorkplanManager
vtf.milestones  // MilestoneManager
vtf.agents      // AgentManager
```

### 4.3 React Hooks

```typescript
import { VtfProvider, useTask, useTasks, useClaimTask, useVtfEvents } from '@vtf/sdk-react';

// Provider wraps the app
<VtfProvider client={vtf}>
  <App />
</VtfProvider>

// Read hooks (built on React Query)
const { data: task, isLoading } = useTask(taskId);
const { data: tasks } = useTasks({ status: 'doing', projectId });
const { data: project } = useProject(projectId);

// Mutation hooks (with optimistic updates)
const { mutate: claim } = useClaimTask();
claim({ taskId, agentId });

// SSE integration (auto-updates React Query cache)
useVtfEvents({ projectId });  // subscribe to project events
```

---

## 5. Implementation Phases

Each phase must pass all tests before the next begins.

### Phase 1: v2 Serializers and API

**Scope:** v2 serializers, URL routing, error standardization, OpenAPI spec, idempotency.

**Deliverables:**
- `src/*/serializers_v2.py` — v2 serializer classes for all entities
- `src/core/versioning.py` — `VersionedSerializerMixin`
- `src/core/errors.py` — Standardized error response handler (one format, always)
- `src/core/idempotency.py` — Idempotency-Key middleware with key storage
- `src/vtaskforge/urls.py` — `/v2/` URL prefix routing via DRF `URLPathVersioning`
- `drf-spectacular` integration — `/v2/schema/`, `/v2/schema/swagger-ui/`, `/v2/schema/redoc/`
- Location header on all 201 Created responses
- Filter param naming standardized (`project_id`, `workplan_id`, etc.)
- Unit tests: every v2 serializer output matches the contract shapes in this document
- Integration tests: v2 endpoints return correct response shapes
- E2E tests: full request/response cycle through v2
- OpenAPI spec snapshot test: generated spec matches expected schema
- **v1 unchanged** — all existing v1 tests still pass

### Phase 2: Python SDK

**Scope:** vtf-sdk-python package with entity types, managers, auth, pagination.

**Deliverables:**
- `vtf-sdk-python/` package (monorepo subfolder initially)
- Entity dataclasses matching Section 1 contracts
- Sync (`VtfClient`) and async (`AsyncVtfClient`) client implementations
- Manager API per Section 3.4
- Exception hierarchy per Section 3.6
- Testing utilities (MockVtfClient, factories, Protocol)
- Unit tests: entity construction from v2 response dicts
- Integration tests: SDK against running v2 API (full lifecycle: create → claim → complete)
- **OpenAPI alignment test:** CI fetches `/v2/schema/`, verifies every SDK entity type matches the spec (Stripe pattern)

### Phase 3: TypeScript SDK

**Scope:** @vtf/sdk and @vtf/sdk-react packages.

**Deliverables:**
- `@vtf/sdk` — core client, entity types, managers, event emitter
- `@vtf/sdk-react` — React Query hooks, SSE → cache bridge, mutation hooks with optimistic updates
- Testing utilities (createMockClient, factories)
- Unit tests: entity construction, type safety
- Integration tests: SDK against running v2 API
- React component tests: hooks return correct entity types
- **OpenAPI alignment test:** CI fetches `/v2/schema/`, verifies TypeScript types match the spec

### Phase 4: Consumer Migration

**Scope:** Migrate each consumer from raw v1 to SDK + v2, one at a time.

- 4a: CLI → vtf-sdk-python
- 4b: vafi controller → vtf-sdk-python (async)
- 4c: MCP tools → v2 serializers (ORM + shared serializer, not SDK)
- 4d: React SPA → @vtf/sdk-react
- Each migration verified by existing E2E tests + new SDK-specific tests

### Phase 5: Deprecate v1

**Scope:** Deprecation headers, monitoring, eventual removal.

- Add `Deprecation: true` and `Sunset: <date>` headers to all v1 responses
- Monitor v1 traffic — confirm zero consumers
- Remove v1 serializers, URL routes, tests
