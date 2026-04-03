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

### 1.1 Base Model

All Python SDK models inherit from a common base that provides immutability and forward compatibility:

```python
from pydantic import BaseModel, ConfigDict

class VtfModel(BaseModel):
    """Base for all vtf SDK models. Frozen (immutable) and forward-compatible."""
    model_config = ConfigDict(frozen=True, extra="ignore")
```

- `frozen=True` — immutable; mutations return new instances (see analysis Gap 12)
- `extra="ignore"` — unknown fields from newer API versions are silently ignored (forward compatibility, see analysis Gap 16)

All ref types and entity types inherit from `VtfModel`. This is defined once, not repeated per class.

### 1.2 Entity Reference Types

Every FK or string-ID reference in a v2 response is one of these shapes. Never a bare ID.

#### ProjectRef

```json
{"id": "xY9kLm2Nq_pRs3tUvWz", "name": "Auth System"}
```

```python
class ProjectRef(VtfModel):
    id: str
    name: str

    def __str__(self) -> str:
        return self.name
```

```typescript
const ProjectRefSchema = z.object({ id: z.string(), name: z.string() }).passthrough();
type ProjectRef = z.infer<typeof ProjectRefSchema>;
```

**Appears in:** Task.project, Workplan.project, Membership.project, Lock.project, ChannelMapping.project

---

#### WorkplanRef

```json
{"id": "aBcDeFgHiJkLmNoPqRs", "name": "Platform Hardening"}
```

```python
class WorkplanRef(VtfModel):
    id: str
    name: str

    def __str__(self) -> str:
        return self.name
```

**Appears in:** Task.workplan, Milestone.workplan

---

#### MilestoneRef

```json
{"id": "zZzYyYxXwWvVuUtTsSr", "name": "Phase 1 Core", "status": "active"}
```

```python
class MilestoneRef(VtfModel):
    id: str
    name: str
    status: Literal["pending", "active", "completed"]

    def __str__(self) -> str:
        return self.name
```

**Appears in:** Task.milestone

**Why status is included:** Milestone status is frequently needed for display (badge color, filtering). Including it avoids a follow-up call for the most common use case.

---

#### TaskRef

```json
{"id": "tsk-abc-123", "title": "Add auth endpoint", "status": "doing"}
```

```python
class TaskRef(VtfModel):
    id: str
    title: str
    status: str

    def __str__(self) -> str:
        return self.title
```

**Appears in:** Task.requires, Link.source (when type=task), Link.target (when type=task), Agent.current_task

**Note:** Tasks use `title` not `name`. All ref types implement `__str__()` returning the display name.

---

#### ActorRef (discriminated union — the single identity reference type)

Every field that references an identity (user or agent) uses ActorRef. The v2 response includes a `type` discriminator:

```json
// Agent identity (pod_name included when available — needed for console terminal)
{"type": "agent", "id": "agt-001", "name": "executor-1", "pod_name": "vafi-executor-7f8b9c"}

// User identity
{"type": "user", "id": "42", "username": "jdoe"}
```

```python
from typing import Annotated, Literal
from pydantic import Discriminator

class AgentActor(VtfModel):
    type: Literal["agent"]
    id: str
    name: str
    pod_name: str | None = None  # k8s pod name, needed for console terminal connection

    def __str__(self) -> str:
        return self.name

class UserActor(VtfModel):
    type: Literal["user"]
    id: str
    username: str

    def __str__(self) -> str:
        return self.username

ActorRef = Annotated[AgentActor | UserActor, Discriminator("type")]
```

```typescript
const ActorRefSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('agent'), id: z.string(), name: z.string(), pod_name: z.string().nullable().default(null) }),
  z.object({ type: z.literal('user'), id: z.string(), username: z.string() }),
]);
type ActorRef = z.infer<typeof ActorRefSchema>;
```

**Appears in all identity fields:**
- Task: `claimed_by`, `assigned_to`, `created_by`
- Review: `reviewer`
- Note: `actor`
- TaskEvent: `triggered_by`
- Project: `owner`, `created_by`
- Workplan: `owner`, `created_by`
- Milestone: `created_by`
- Membership: `user`
- Lock: `user`

**Why one type for all identities (no separate AgentRef/UserRef):**
- `claimed_by` is always an agent today, but the field is a CharField, not a FK — it could hold a user ID in the future
- `owner` is always a user today, but the discriminator makes it explicit rather than assumed
- One type means one SDK contract — consumers handle identity display the same way everywhere: `str(actor)` returns the name/username
- The `type` discriminator enables type narrowing when needed: `if actor.type == "agent": ...`
- Follows Liskov Substitution: any ActorRef is displayable without knowing its concrete type

**Resolution of string ID fields:** `claimed_by`, `assigned_to`, `created_by`, `reviewer_id`, `actor_id`, `triggered_by` are all CharField on the Django model (not FK). The v2 serializer resolves them via batch lookup — first against the Agent table, then the User table, falling back to a degraded ref `{"type": "agent", "id": "original-value", "name": "original-value"}` if the entity no longer exists.

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
class TaskLinkRef(BaseModel, frozen=True):
    type: Literal["task"]
    id: str
    title: str
    status: str

    def __str__(self) -> str:
        return self.title

class MilestoneLinkRef(BaseModel, frozen=True):
    type: Literal["milestone"]
    id: str
    name: str
    status: str

    def __str__(self) -> str:
        return self.name

class WorkplanLinkRef(BaseModel, frozen=True):
    type: Literal["workplan"]
    id: str
    name: str

    def __str__(self) -> str:
        return self.name

class ExternalLinkRef(BaseModel, frozen=True):
    type: Literal["commit", "jira", "doc", "file", "area"]
    id: str
    label: str

    def __str__(self) -> str:
        return self.label

InternalLinkRef = Annotated[
    TaskLinkRef | MilestoneLinkRef | WorkplanLinkRef,
    Discriminator("type"),
]

LinkRef = Annotated[
    TaskLinkRef | MilestoneLinkRef | WorkplanLinkRef | ExternalLinkRef,
    Discriminator("type"),
]
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

### 1.3 Permissions Object

Every v2 entity response includes a `permissions` object describing what the authenticated user can do. This is server-computed metadata — the SDK exposes it but never duplicates the authorization logic (see analysis Gap 11).

```json
{
  "id": "tsk-abc",
  "title": "Add auth endpoint",
  "status": "todo",
  "permissions": {
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

### 1.4 Null Contract

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

### 1.5 Error Contract

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

### 2.3 Field Naming: snake_case in Both SDKs

The v2 API uses `snake_case` for all field names. Both SDKs preserve snake_case rather than converting to camelCase (TypeScript convention).

**Rationale:**
- Consistency: the SDK field names match what you see in the browser network tab and API docs
- No mapping layer: a camelCase transform is a whole layer that can drift and introduces debugging confusion
- Precedent: GitHub's Octokit SDK uses snake_case matching the API
- Simplicity over convention: snake_case works in TypeScript, it's just not the usual style

```typescript
// TypeScript SDK uses snake_case (matches API)
task.claimed_by?.name;    // not task.claimedBy
task.created_at;          // not task.createdAt
task.project.name;        // same in both languages
```

```python
# Python SDK uses snake_case (natural)
task.claimed_by.name
task.created_at
task.project.name
```

### 2.4 Global Conventions

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

### 2.5 Entity Response Shapes

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
  "assigned_to": {"type": "agent", "id": "agt-001", "name": "executor-1", "pod_name": null},
  "claimed_by": {"type": "agent", "id": "agt-001", "name": "executor-1", "pod_name": "vafi-executor-7f8b9c"},
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
  "permissions": {
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
  "permissions": {
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
  "permissions": {
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
  "permissions": {
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

**Notes:**
- Agent already uses the TaskRef pattern for `current_task` in v1. v2 preserves this.
- Agent has both `registered_at` (domain event: when agent registered with the system) and `created_at` (infrastructure: when row was inserted). These currently coincide but are semantically distinct — if agents were pre-provisioned by an admin, `created_at` would be the provisioning time while `registered_at` would be when the agent first authenticated. Same rationale applies to `ExternalIdentity.linked_at`, `SessionRecord.started_at` — domain timestamps are preserved alongside infrastructure timestamps.

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

#### Membership (v2)

`GET /v2/projects/{id}/members/`

```json
{
  "results": [
    {
      "id": 1,
      "user": {"type": "user", "id": "42", "username": "jdoe"},
      "project": {"id": "xY9...", "name": "Auth System"},
      "role": "owner",
      "created_at": "2026-03-01T00:00:00Z"
    }
  ],
  "next": null,
  "previous": null
}
```

**Change from v1:** `user_id` and `project_id` (bare IDs) → `user` (ActorRef) and `project` (ProjectRef).

---

#### Lock (v2)

`GET /v2/locks/`

```json
{
  "results": [
    {
      "id": 1,
      "project": {"id": "xY9...", "name": "Auth System"},
      "role": "architect",
      "user": {"type": "user", "id": "42", "username": "jdoe"},
      "session_id": "sess-abc",
      "created_at": "2026-04-03T10:00:00Z",
      "last_activity": "2026-04-03T10:15:00Z"
    }
  ],
  "next": null,
  "previous": null
}
```

**Change from v1:** `project_id` (bare string) → `project` (ProjectRef). `user` (username string) → `user` (ActorRef).

---

#### ChannelMapping (v2)

`GET /v2/channel-mappings/`

```json
{
  "results": [
    {
      "id": 1,
      "provider": "slack",
      "channel_id": "C1234567890",
      "channel_name": "#dev",
      "project": {"id": "xY9...", "name": "Auth System"},
      "created_at": "2026-04-03T10:00:00Z"
    }
  ],
  "next": null,
  "previous": null
}
```

**Change from v1:** `project_id` (bare string) → `project` (ProjectRef).

---

#### User Detail (v2)

`GET /v2/users/{id}/`

```json
{
  "id": 42,
  "username": "jdoe",
  "user_type": "human",
  "is_staff": false,
  "is_active": true,
  "date_joined": "2026-01-01T00:00:00Z",
  "last_login": "2026-04-03T09:00:00Z",
  "memberships": [
    {
      "project": {"id": "xY9...", "name": "Auth System"},
      "role": "owner"
    }
  ]
}
```

**Change from v1:** `project_id` in memberships (bare string) → `project` (ProjectRef).

---

#### Link Write Shape (v2)

`POST /v2/links/` — write accepts flat IDs (read returns nested objects):

```json
{
  "source_type": "task",
  "source_id": "tsk-abc",
  "target_type": "task",
  "target_id": "tsk-def",
  "link_type": "depends_on"
}
```

Response returns the Link entity with embedded `source` and `target` objects (see Link v2 shape above).

---

### 2.6 SSE Event Payload (v2)

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
  pyproject.toml            # pydantic>=2.0, httpx
  vtf_sdk/
    __init__.py             # VtfClient, AsyncVtfClient
    client.py               # Client implementations (sync + async)
    entities.py             # Task, Project, Workplan, Milestone, Agent, etc. (Pydantic models)
    refs.py                 # ProjectRef, WorkplanRef, ActorRef, LinkRef, etc. (Pydantic models)
    managers.py             # TaskManager, ProjectManager, etc.
    exceptions.py           # Domain exception hierarchy (plain Python)
    auth.py                 # TokenAuth, OAuthAuth, auth strategies
    pagination.py           # PagedResult (Pydantic), lazy iterator
    protocols.py            # VtfClientProtocol, manager protocols (typing.Protocol)
    testing/
      __init__.py           # MockVtfClient, factories
      mock_client.py        # In-memory client implementation
      factories.py          # build_task, build_project, etc.
```

**Dependencies:** `pydantic>=2.0`, `httpx>=0.27` (sync and async HTTP client)

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

All entities inherit from `VtfModel` (Section 1.1) — frozen, forward-compatible Pydantic v2 models. Mutations return new instances. Construction from API response dicts uses `model_validate()` — Pydantic handles recursive parsing, null fields, and discriminated unions automatically.

#### Task (the most complex entity — shown in full)

```python
from datetime import datetime, timedelta

class TaskPermissions(VtfModel):
    can_edit: bool
    can_delete: bool
    available_actions: list[str]

class Task(VtfModel):
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

    # Expandable collections (?expand=links,reviews,events,traces)
    # None = not requested. [] = requested but empty.
    links: list['Link'] | None = None
    reviews: list['Review'] | None = None
    events: list['TaskEvent'] | None = None
    traces: list[dict] | None = None

    def __str__(self) -> str:
        return self.title
```

**Usage:**
```python
task = Task.model_validate(response_dict)
task.project.name           # "Auth System" — ProjectRef, parsed automatically
str(task.claimed_by)        # "executor-1" — AgentActor.__str__()
task.requires[0].title      # "Create user model" — list[TaskRef]
task.reviews                # None (not expanded) or list[Review] (expanded)
```

#### Other Entities (same pattern, key fields listed)

```python
class Project(VtfModel):
    id: str
    name: str
    description: str
    status: str
    repo_url: str
    default_branch: str
    tags: list[str]
    owner: ActorRef
    created_by: ActorRef
    permissions: 'ProjectPermissions'
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str:
        return self.name

class Workplan(VtfModel):
    id: str
    name: str
    description: str
    status: str
    project: ProjectRef
    owner: ActorRef
    tags: list[str]
    target_date: datetime | None
    default_needs_review_before_start: bool   # NOT nullable (default=False in model)
    default_needs_review_on_completion: bool   # NOT nullable (default=False in model)
    created_by: ActorRef
    permissions: 'WorkplanPermissions'
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str:
        return self.name

class Milestone(VtfModel):
    id: str
    name: str
    description: str
    status: str
    order: int
    workplan: WorkplanRef
    default_needs_review_before_start: bool | None
    default_needs_review_on_completion: bool | None
    created_by: ActorRef
    permissions: 'MilestonePermissions'
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str:
        return self.name

class Agent(VtfModel):
    id: str
    name: str
    tags: list[str]
    status: str
    effective_status: str
    last_heartbeat: datetime | None
    pod_name: str
    registered_at: datetime
    current_task: TaskRef | None
    tasks_completed: int
    tasks_failed: int
    created_at: datetime
    updated_at: datetime

    def __str__(self) -> str:
        return self.name

class Review(VtfModel):
    id: str
    task: TaskRef
    decision: str
    reason: str
    reviewer: ActorRef
    reviewer_type: str
    created_at: datetime
    updated_at: datetime

class Note(VtfModel):
    id: str
    task: TaskRef
    text: str
    actor: ActorRef
    created_at: datetime

class Link(VtfModel):
    id: str
    source: InternalLinkRef
    target: LinkRef
    link_type: str
    metadata: dict | None
    created_by: ActorRef
    created_at: datetime
    updated_at: datetime

class TaskEvent(VtfModel):
    id: str
    task: TaskRef
    event_type: str
    data: dict
    triggered_by: ActorRef
    timestamp: datetime
```

**Why Pydantic over dataclasses:**
- `model_validate(dict)` replaces manual `from_dict()` with recursive nested parsing
- Discriminated unions (ActorRef, LinkRef) handled natively via `Discriminator`
- Validation on construction catches API contract violations immediately
- `VtfModel` base provides `extra="ignore"` for forward compatibility everywhere
- `model_dump()` serializes back to dict for debugging and testing
- `frozen=True` enforces immutability (same as frozen dataclasses)

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

### 3.5 Async Manager API

`AsyncVtfClient` provides the same manager interface as `VtfClient`, with `async` methods:

```python
# AsyncTaskManager mirrors TaskManager exactly, but all methods are async
vtf = AsyncVtfClient(url="...", token="...")
task = await vtf.tasks.get(task_id)
task = await vtf.tasks.claim(task_id, agent_id=agent_id)
tasks = await vtf.tasks.list(status="doing")

# list_all returns an async iterator
async for task in vtf.tasks.list_all(status="doing"):
    print(task.title)
```

Both sync and async managers share entity construction logic via `BaseTaskManager._build_task()` — only the HTTP transport differs (see analysis Gap 2).

### 3.6 Pagination

```python
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

class PagedResult(BaseModel, Generic[T], frozen=True):
    items: list[T]
    has_more: bool
    next_cursor: str | None = None
    previous_cursor: str | None = None
```

### 3.7 Exception Hierarchy

Exceptions are plain Python classes (not Pydantic models) — they extend `Exception` and carry structured context from the API error response.

```python
class VtfError(Exception):
    """Base for all SDK exceptions."""
    def __init__(self, code: str, message: str, details: dict | None = None):
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

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

### 4.1 Runtime Validation with Zod

TypeScript interfaces are compile-time only — erased at runtime. If the API returns an unexpected shape, the error surfaces at render time, not parse time. **Zod** provides runtime validation for TypeScript, equivalent to Pydantic in Python.

Zod schemas define the runtime validation AND infer the TypeScript types — no duplication:

```typescript
import { z } from 'zod';

// ── Reference schemas ──────────────────────────────────
const ProjectRefSchema = z.object({
  id: z.string(),
  name: z.string(),
});
type ProjectRef = z.infer<typeof ProjectRefSchema>;

const WorkplanRefSchema = z.object({
  id: z.string(),
  name: z.string(),
});
type WorkplanRef = z.infer<typeof WorkplanRefSchema>;

const MilestoneRefSchema = z.object({
  id: z.string(),
  name: z.string(),
  status: z.enum(['pending', 'active', 'completed']),
});
type MilestoneRef = z.infer<typeof MilestoneRefSchema>;

const TaskRefSchema = z.object({
  id: z.string(),
  title: z.string(),
  status: z.string(),
});
type TaskRef = z.infer<typeof TaskRefSchema>;

// ── Discriminated unions ───────────────────────────────
const AgentActorSchema = z.object({
  type: z.literal('agent'),
  id: z.string(),
  name: z.string(),
  pod_name: z.string().nullable().default(null),
});

const UserActorSchema = z.object({
  type: z.literal('user'),
  id: z.string(),
  username: z.string(),
});

const ActorRefSchema = z.discriminatedUnion('type', [
  AgentActorSchema,
  UserActorSchema,
]);
type ActorRef = z.infer<typeof ActorRefSchema>;

// ── Full entity schema ─────────────────────────────────
const TaskPermissionsSchema = z.object({
  can_edit: z.boolean(),
  can_delete: z.boolean(),
  available_actions: z.array(z.string()),
});

const TaskSchema = z.object({
  id: z.string(),
  title: z.string(),
  description: z.string(),
  status: z.string(),
  project: ProjectRefSchema,
  workplan: WorkplanRefSchema.nullable(),
  milestone: MilestoneRefSchema.nullable(),
  labels: z.array(z.string()),
  acceptance_criteria: z.array(z.string()),
  needs_review_before_start: z.boolean().nullable(),
  needs_review_on_completion: z.boolean().nullable(),
  review_return_to: z.string().nullable(),
  requires: z.array(TaskRefSchema),
  assigned_to: ActorRefSchema.nullable(),
  claimed_by: ActorRefSchema.nullable(),
  claimed_at: z.string().nullable(),
  claim_timeout: z.string().nullable(),       // ISO 8601 duration
  claim_expires_at: z.string().nullable(),
  created_by: ActorRefSchema.nullable(),
  spec: z.string(),
  agent_model: z.string(),
  test_command: z.record(z.unknown()),
  judge: z.boolean(),
  isolation: z.string(),
  retry_count: z.number(),
  execution_summary: z.record(z.unknown()).nullable(),
  permissions: TaskPermissionsSchema,
  created_at: z.string(),
  updated_at: z.string(),
  // Expandable collections (null = not requested, [] = requested but empty)
  links: z.array(z.lazy(() => LinkSchema)).nullable().default(null),
  reviews: z.array(z.lazy(() => ReviewSchema)).nullable().default(null),
  events: z.array(z.lazy(() => TaskEventSchema)).nullable().default(null),
  traces: z.array(z.record(z.unknown())).nullable().default(null),
}).passthrough();  // forward-compatible: ignore unknown fields

type Task = z.infer<typeof TaskSchema>;

// Usage — one line, validated at runtime:
const task = TaskSchema.parse(apiResponseJson);
task.project.name;  // string — guaranteed at parse time, not render time
```

**The Pydantic ↔ Zod parallel:**

| Concern | Python (Pydantic) | TypeScript (Zod) |
|---------|-------------------|------------------|
| Schema definition | `class ProjectRef(BaseModel)` | `const ProjectRefSchema = z.object({...})` |
| Type derivation | Class IS the type | `type ProjectRef = z.infer<typeof ProjectRefSchema>` |
| Parsing | `Task.model_validate(dict)` | `TaskSchema.parse(json)` |
| Discriminated unions | `Discriminator("type")` | `z.discriminatedUnion("type", [...])` |
| Nullable fields | `field: Type \| None` | `Schema.nullable()` |
| Forward compatibility | `extra = "ignore"` | `.passthrough()` |
| Validation errors | `ValidationError` | `ZodError` with path + message |

### 4.2 Package Structure

```
@vtf/sdk/
  package.json              # zod, dependencies
  src/
    index.ts                # VtfClient
    client.ts               # Client implementation
    schemas/
      refs.ts               # Zod schemas for all ref types
      task.ts               # TaskSchema, TaskPermissionsSchema
      project.ts            # ProjectSchema
      workplan.ts           # WorkplanSchema
      milestone.ts          # MilestoneSchema
      agent.ts              # AgentSchema
      review.ts             # ReviewSchema
      note.ts               # NoteSchema
      link.ts               # LinkSchema
      event.ts              # TaskEventSchema
      errors.ts             # ApiErrorSchema
    types.ts                # z.infer<> type exports (Task, Project, etc.)
    managers.ts             # TaskManager, ProjectManager, etc.
    exceptions.ts           # VtfError class hierarchy
    auth.ts                 # Auth strategies
    pagination.ts           # PagedResult schema
    events.ts               # SSE event emitter (framework-agnostic)
  testing/
    index.ts                # createMockClient, factories
    mock-client.ts          # In-memory implementation
    factories.ts            # buildTask, buildProject, etc.

@vtf/sdk-react/
  package.json              # @vtf/sdk, @tanstack/react-query
  src/
    index.ts                # hooks, provider
    provider.ts             # VtfProvider (React context with VtfClient)
    hooks/
      useTask.ts            # single task by ID
      useTasks.ts           # task list with filters
      useTasksPage.ts       # paginated task list
      useProject.ts         # single project by ID
      useProjects.ts        # project list
      useWorkplan.ts        # single workplan by ID
      useMilestone.ts       # single milestone by ID
      useAgents.ts          # agent list
      useVtfEvents.ts       # SSE → React Query cache bridge
    mutations/
      useClaimTask.ts       # with optimistic update
      useSubmitTask.ts
      useCompleteTask.ts
      useCreateTask.ts
      useUpdateTask.ts
      ...
```

**Dependencies:**
- `@vtf/sdk`: `zod>=3.22`
- `@vtf/sdk-react`: `@vtf/sdk`, `@tanstack/react-query>=5.0`, `react>=18`

### 4.3 Core Manager API (framework-agnostic)

The core `@vtf/sdk` package provides managers with the same interface as the Python SDK. These are `async` (returning Promises) since TypeScript HTTP is inherently async:

```typescript
class TaskManager {
  // Read
  get(id: string, options?: { expand?: string[] }): Promise<Task>;
  list(filters?: TaskFilters): Promise<PagedResult<Task>>;
  listAll(filters?: TaskFilters): AsyncIterable<Task>;
  claimable(filters?: { tags?: string[]; project_id?: string }): Promise<PagedResult<Task>>;

  // State transitions (return updated Task)
  submit(id: string): Promise<Task>;
  claim(id: string, params: { agent_id: string }): Promise<Task>;
  unclaim(id: string): Promise<Task>;
  complete(id: string): Promise<Task>;
  fail(id: string): Promise<Task>;
  recover(id: string, params: { target: string }): Promise<Task>;
  block(id: string, params?: { reason?: string }): Promise<Task>;
  unblock(id: string): Promise<Task>;
  defer(id: string): Promise<Task>;
  cancel(id: string): Promise<Task>;
  heartbeat(id: string): Promise<void>;

  // Write
  create(params: CreateTaskParams): Promise<Task>;
  update(id: string, params: Partial<UpdateTaskParams>): Promise<Task>;
  delete(id: string): Promise<void>;

  // Notes
  listNotes(taskId: string): Promise<PagedResult<Note>>;
  addNote(taskId: string, params: { text: string }): Promise<Note>;

  // Reviews
  listReviews(taskId: string): Promise<PagedResult<Review>>;
  submitReview(taskId: string, params: SubmitReviewParams): Promise<Review>;
}
```

The React hooks in `@vtf/sdk-react` wrap these managers — they don't contain their own HTTP logic:

```typescript
// useTask internally calls: vtfClient.tasks.get(id)
// useClaimTask internally calls: vtfClient.tasks.claim(id, params)
```

### 4.4 Client

```typescript
import { VtfClient } from '@vtf/sdk';

const vtf = new VtfClient({
  baseUrl: 'https://vtf.example.com',
  token: '...',
  // or: credentials: 'include' (for session auth in browser)
  retry: { maxRetries: 3, backoffFactor: 0.5, retryOn: [429, 503] },
  timeout: 30_000,  // ms
});

vtf.projects    // ProjectManager
vtf.tasks       // TaskManager
vtf.workplans   // WorkplanManager
vtf.milestones  // MilestoneManager
vtf.agents      // AgentManager
```

### 4.5 React Hooks

```typescript
import { VtfProvider, useTask, useTasks, useClaimTask, useVtfEvents } from '@vtf/sdk-react';

// Provider wraps the app — injects VtfClient into React context
<VtfProvider client={vtf}>
  <App />
</VtfProvider>

// Read hooks (built on React Query, responses validated via Zod)
const { data: task, isLoading } = useTask(taskId);
task?.project.name;  // string — Zod-validated at fetch time

const { data: tasks } = useTasks({ status: 'doing', projectId });
const { data: project } = useProject(projectId);

// Paginated hooks
const { data, fetchNextPage, hasNextPage } = useInfiniteTasks({ status: 'doing' });

// Mutation hooks (with optimistic updates)
const { mutate: claim } = useClaimTask();
claim({ taskId, agentId });

// SSE integration (auto-updates React Query cache)
useVtfEvents({ projectId });  // subscribe to project events, merge into cache
```

---

## 5. Cross-Cutting Concerns (Both SDKs)

These apply to both the Python and TypeScript SDKs.

### 5.1 Retry with Exponential Backoff

Network failures and transient server errors (429, 503) are retried automatically with exponential backoff. Retries are configurable at client construction time.

**Python:**
```python
vtf = VtfClient(
    url="...",
    token="...",
    retry=RetryConfig(
        max_retries=3,
        backoff_factor=0.5,   # delays: 0.5s, 1.0s, 2.0s
        retry_on_status=[429, 503],
    ),
)
```

**TypeScript:**
```typescript
const vtf = new VtfClient({
  baseUrl: '...',
  token: '...',
  retry: { maxRetries: 3, backoffFactor: 0.5, retryOn: [429, 503] },
});
```

**Rules:**
- Only retry idempotent requests (GET) and requests with `Idempotency-Key` header
- Non-idempotent POST without Idempotency-Key: do NOT retry (could cause duplicates)
- Respect `Retry-After` header from 429 responses
- Max total retry time capped (e.g., 30s) to prevent infinite waits

### 5.2 Request Timeout

Configurable per-client, with a sensible default:

```python
vtf = VtfClient(url="...", token="...", timeout=30.0)  # seconds
```

```typescript
const vtf = new VtfClient({ baseUrl: '...', token: '...', timeout: 30_000 });  // ms
```

Default: 30 seconds. Heartbeat endpoint may need a shorter timeout (5s).

### 5.3 User-Agent Header

Every SDK request includes a User-Agent header for server-side debugging and traffic analysis:

```
User-Agent: vtf-sdk-python/0.1.0
User-Agent: vtf-sdk-ts/0.1.0
```

Helps the server distinguish SDK traffic from raw API calls, identify SDK version distribution, and debug consumer-specific issues.

### 5.4 Request Logging

Structured logging for debugging API calls — off by default, enabled via configuration.

**Python:**
```python
import logging
logging.getLogger("vtf_sdk").setLevel(logging.DEBUG)

# Output:
# vtf_sdk: POST /v2/tasks/tsk-abc/claim/ → 200 (143ms)
# vtf_sdk: GET /v2/tasks/?status=doing&project_id=xY9... → 200 (89ms) [23 results]
```

**TypeScript:**
```typescript
const vtf = new VtfClient({ baseUrl: '...', token: '...', debug: true });

// Console output:
// [vtf-sdk] POST /v2/tasks/tsk-abc/claim/ → 200 (143ms)
```

Logs include: method, path, status code, duration. Request/response bodies are NOT logged by default (may contain sensitive data). A `verbose` level can be enabled to include bodies.

### 5.5 py.typed Marker (Python SDK)

The Python SDK includes an empty `vtf_sdk/py.typed` file for PEP 561 compliance. This allows type checkers (`mypy`, `pyright`) to recognize the SDK's type annotations when installed as a package.

### 5.6 SDK Version Reporting

Both SDKs expose their version programmatically:

```python
import vtf_sdk
vtf_sdk.__version__  # "0.1.0"
```

```typescript
import { VERSION } from '@vtf/sdk';
console.log(VERSION);  // "0.1.0"
```

---

## 6. Implementation Phases

Each phase must pass all tests before the next begins.

### Phase 0: Identity Field Migration (PREREQUISITE)

**Scope:** Formalize Agent ↔ User relationship, convert all identity CharFields to User ForeignKeys. This is a v1 model change — prerequisite for v2 ActorRef to work correctly.

**Why this must come first:** The v2 ActorRef pattern requires identity fields to be proper entity references, not arbitrary strings. The current CharField identity fields (`claimed_by`, `created_by`, `owner`, `reviewer_id`, `actor_id`) store inconsistent values (nanoids, usernames, free text) that cannot be reliably resolved. See analysis doc "Critical Finding: Identity Fields Are Unstructured."

**Deliverables:**
- `Agent.user` — OneToOneField FK to Django User (formalizes the implicit username=agent.id link)
- All identity fields converted from CharField to FK User:
  - Task: `claimed_by`, `assigned_to`, `created_by`
  - Project: `owner`, `created_by`
  - Workplan: `owner`, `created_by`
  - Milestone: `created_by`
  - Review: `reviewer_id` → rename to `reviewer`, FK User
  - Note: `actor_id` → rename to `actor`, FK User
  - Link: `created_by`
- `TaskEvent.triggered_by` — remains CharField (NOT an identity field — stores action labels)
- Rename `TaskEvent.triggered_by` → `trigger_source` to clarify it's not an entity reference
- Data migrations:
  - Link existing Agents to Users via `User.objects.get(username=agent.id)`
  - Resolve CharField username values to User PKs
  - Handle unresolvable values (set to null with migration log)
- All views updated to set FK from `request.user` instead of string values
- All existing v1 tests updated and passing
- v1 serializers updated (CharField → PrimaryKeyRelatedField, backward-compatible on write)

### Phase 1: v2 Serializers and API

**Scope:** v2 serializers, URL routing, error standardization, OpenAPI spec, idempotency. Depends on Phase 0 (identity FKs must exist for ActorRef resolution).

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

**Scope:** vtf-sdk-python package with Pydantic entity types, managers, auth, pagination.

**Deliverables:**
- `vtf-sdk-python/` package (monorepo subfolder initially)
- Pydantic v2 entity models matching Section 1 contracts
- Sync (`VtfClient`) and async (`AsyncVtfClient`) client implementations via httpx
- Manager API per Section 3.4
- Exception hierarchy per Section 3.6
- Retry with backoff, timeout, User-Agent, request logging (Section 5)
- Testing utilities (MockVtfClient, factories, Protocol)
- `py.typed` marker for PEP 561 compliance
- Unit tests: `model_validate()` from v2 response dicts, discriminated union dispatch
- Integration tests: SDK against running v2 API (full lifecycle: create → claim → complete)
- **OpenAPI alignment test:** CI fetches `/v2/schema/`, verifies every Pydantic model matches the spec

### Phase 3: TypeScript SDK

**Scope:** @vtf/sdk (Zod schemas + client) and @vtf/sdk-react (hooks + SSE).

**Deliverables:**
- `@vtf/sdk` — Zod schemas, inferred types, client, managers, event emitter
- `@vtf/sdk-react` — React Query hooks, SSE → cache bridge, mutation hooks with optimistic updates, VtfProvider
- Retry with backoff, timeout, User-Agent, request logging (Section 5)
- Testing utilities (createMockClient, factories)
- Unit tests: `Schema.parse()` from v2 response JSON, discriminated union dispatch
- Integration tests: SDK against running v2 API
- React component tests: hooks return Zod-validated entity types
- **OpenAPI alignment test:** CI fetches `/v2/schema/`, verifies Zod schemas match the spec

### Phase 4: Consumer Migration

**Scope:** Migrate each consumer from raw v1 to SDK + v2, one at a time.

- 4a: CLI → vtf-sdk-python (Pydantic entities, sync VtfClient)
- 4b: vafi controller → vtf-sdk-python (Pydantic entities, async AsyncVtfClient)
- 4c: MCP tools → v2 serializers (ORM + shared serializer, not SDK)
- 4d: React SPA → @vtf/sdk-react (Zod-validated entities, React Query hooks)
- Each migration verified by existing E2E tests + new SDK-specific tests

### Phase 5: Deprecate v1

**Scope:** Deprecation headers, monitoring, eventual removal.

- Add `Deprecation: true` and `Sunset: <date>` headers to all v1 responses
- Monitor v1 traffic — confirm zero consumers
- Remove v1 serializers, URL routes, tests
