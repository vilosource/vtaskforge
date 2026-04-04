# Phase 1: v2 API Layer — Implementation Plan

**Date:** 2026-04-04
**Status:** Draft
**Prerequisite:** [phase0-identity-authorization-DESIGN.md](phase0-identity-authorization-DESIGN.md) (COMPLETE)
**Contract spec:** [v2-api-sdk-DESIGN.md](v2-api-sdk-DESIGN.md) (Sections 1–2)
**Process:** [milestone-process-GUIDE.md](../guides/milestone-process-GUIDE.md) + Phase 0 verification process

---

## 1. Overview

Phase 0 (identity FK migration + authorization enforcement) is complete and deployed to vtf-dev. All identity fields are FK User, all endpoints enforce project-scoped authorization. The codebase has 1497 tests, 0 failures.

Phase 1 adds the v2 API layer on top of this foundation:

- **Embedded entity references** — every FK returns a typed ref object (`ProjectRef`, `ActorRef`, etc.) instead of bare IDs or username strings
- **Permissions objects** — every entity response includes server-computed `permissions` describing what the authenticated user can do
- **Standardized errors** — one error format across all v2 endpoints
- **API versioning** — same ViewSets serve both `/v1/` and `/v2/`
- **OpenAPI spec** — auto-generated from v2 serializers via `drf-spectacular`
- **Idempotency** — `Idempotency-Key` header honored on v2 POST mutations
- **v1 unchanged** — all existing tests and consumers continue working

The contract shapes for all v2 entities are defined in [v2-api-sdk-DESIGN.md](v2-api-sdk-DESIGN.md). This document defines the **implementation steps**, their **ordering**, and the **Definition of Done** for each step.

---

## 2. Current State

| Component | State |
|-----------|-------|
| Serializers | 7 v1 files using `SlugRelatedField` (username strings), bare PKs for entity refs |
| Views | ViewSets with `select_related` for identity FKs, authorization via `ProjectScopedPermission` + `RoleBasedPermission` |
| Settings | DRF: JSONRenderer, TokenAuth+SessionAuth, `VTFCursorPagination`. No versioning. No OpenAPI. |
| URL routing | All under `path('v1/', ...)` in `src/vtaskforge/urls.py` |
| Requirements | Django 5.1, DRF 3.15, no `drf-spectacular` |
| Test baseline | 1497 test functions, 0 failures |

---

## 3. Architecture

```
Request → URLPathVersioning (v1 or v2)
  │
  ├── ViewSet.get_serializer_class()
  │     ├── v1 → existing serializer (unchanged)
  │     └── v2 → new serializer_v2 (embedded refs + permissions)
  │
  ├── Exception handler
  │     ├── v1 → DRF default format (unchanged)
  │     └── v2 → standardized {error: {code, message, details, field_errors}}
  │
  └── Idempotency middleware (v2 POST only)
```

Key design decisions:

1. **Same ViewSets** — no duplicate views. `VersionedSerializerMixin` on each ViewSet inspects `request.version` and returns the appropriate serializer class.
2. **Separate serializer files** — each app gets a `serializers_v2.py` alongside the existing `serializers.py`. No modifications to v1 serializers.
3. **Shared ref types** — `core/refs.py` defines all ref serializers (`ProjectRef`, `ActorRef`, etc.) used by every v2 serializer.
4. **Shared permissions computer** — `core/permissions_computer.py` computes the `permissions` object for each entity type.
5. **Write shape unchanged** — POST/PATCH accepts bare IDs (same as v1 write). Only read responses change.

---

## 4. Verification Process

Every step follows this exact 8-step sequence. No step is done until every criterion is met. No steps may be skipped. No items within a step may be silently omitted.

```
1. TDD TESTS (RED)
   - Write ALL new test functions for this step
   - Run them: they must ALL FAIL (red)
   - If any pass before implementation, the test is wrong

2. IMPLEMENT
   - Create/modify files per the step spec
   - Follow existing patterns and conventions

3. TDD TESTS (GREEN)
   - Run the new tests: they must ALL PASS
   - If any fail, fix the implementation (not the test)

4. FULL REGRESSION
   - Run: pytest tests/ -q --tb=short
   - ALL existing tests must pass (baseline: 1497+)
   - If tests fail, fix the code, not the tests' intent

5. INTEGRATION VERIFICATION
   - Start Postgres: docker compose up -d db
   - Run: DATABASE_URL=... pytest tests/ -q --tb=short
   - Verify all passes against real database

6. BUILD + DEPLOY TO TEST
   - Build image: docker build -f Dockerfile.prod -t harbor.viloforge.com/vafi/vtf:$(git rev-parse --short HEAD) .
   - Push: docker push harbor.viloforge.com/vafi/vtf:<hash>
   - Deploy: kubectl set image deployment/vtf-api -n vtf-dev vtf-api=harbor.viloforge.com/vafi/vtf:<hash>

7. E2E VERIFICATION
   - Run E2E suite against deployed stack
   - Each step has specific E2E criteria in its DoD table
   - If E2E fails, diagnose on deployed stack

8. DEFINITION OF DONE REVIEW
   - Walk through EVERY DoD item for this step
   - Check each one: pass or fail, with evidence
   - ALL must pass. If any fail, go back to step 2
   - Only after ALL pass: commit, journal, move to next step
```

---

## 5. Step Dependency Graph

```
Step 1 (URL routing + versioning)
  │
  ├──→ Step 2 (VersionedSerializerMixin + error handler)
  │      │
  │      └──→ Step 5 (Project/Workplan/Milestone v2) ──→ Step 6 (Agent/Review/Note/Event v2)
  │                                                   ──→ Step 7 (Link v2)
  │                                                   ──→ Step 8 (Task v2) ← depends on 6, 7
  │                                                   ──→ Step 9 (Prefs v2)
  │
  ├──→ Step 3 (Ref serializers) ──→ Steps 5-9
  │
  ├──→ Step 4 (Permissions computer) ──→ Steps 5-9
  │
  └──→ Step 10 (OpenAPI + Idempotency + Location) ← depends on 1-9
```

Steps 1-4 are infrastructure (can be done sequentially, each building on the last).
Steps 5-7, 9 can be parallelized after 1-4 are complete.
Step 8 (Task) depends on 6 and 7 (for expand support).
Step 10 is the capstone — requires all serializers to exist.

---

## 6. Implementation Steps

### Step 1: URL Routing and DRF Versioning Infrastructure

**Scope:** Enable `URLPathVersioning` in DRF settings. Add `/v2/` URL patterns mirroring all `/v1/` routes. At this stage, `/v2/` returns identical v1 output — validates routing plumbing only.

**Depends on:** Nothing (first step).

**Files:**

| Action | Path |
|--------|------|
| MODIFY | `src/vtaskforge/settings/base.py` — add versioning to `REST_FRAMEWORK` |
| MODIFY | `src/vtaskforge/urls.py` — add `path('v2/', ...)` for all app includes and standalone views |
| CREATE | `tests/core/test_v2_routing.py` |

**Settings addition:**
```python
'DEFAULT_VERSIONING_CLASS': 'rest_framework.versioning.URLPathVersioning',
'ALLOWED_VERSIONS': ['v1', 'v2'],
'DEFAULT_VERSION': 'v1',
```

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_v2_tasks_list_200` | `GET /v2/tasks/` → 200 |
| 2 | `test_v2_projects_list_200` | `GET /v2/projects/` → 200 |
| 3 | `test_v2_workplans_list_200` | `GET /v2/workplans/` → 200 |
| 4 | `test_v2_milestones_list_200` | `GET /v2/milestones/` → 200 |
| 5 | `test_v2_agents_list_200` | `GET /v2/agents/` → 200 |
| 6 | `test_v2_events_list_200` | `GET /v2/events/` → 200 |
| 7 | `test_v2_links_list_200` | `GET /v2/links/` → 200 |
| 8 | `test_v2_task_notes_200` | `GET /v2/tasks/{id}/notes/` → 200 |
| 9 | `test_v2_task_reviews_200` | `GET /v2/tasks/{id}/reviews/` → 200 |
| 10 | `test_v2_task_events_200` | `GET /v2/tasks/{id}/events/` → 200 |
| 11 | `test_v2_auth_validate_200` | `GET /v2/auth/validate/` → 200 |
| 12 | `test_v2_locks_200` | `GET /v2/locks/` → 200 |
| 13 | `test_v2_channel_mappings_200` | `GET /v2/channel-mappings/` → 200 |
| 14 | `test_v2_health_200` | `GET /v2/health` → 200 |
| 15 | `test_request_version_v2` | View accessed via `/v2/` has `request.version == 'v2'` |
| 16 | `test_request_version_v1` | View accessed via `/v1/` has `request.version == 'v1'` |
| 17 | `test_v3_not_allowed` | `GET /v3/tasks/` → 404 or 406 (unregistered version) |

**Integration:**
- [ ] `curl /v2/tasks/` returns same shape as `/v1/tasks/`

**Regression:**
- [ ] All 1497 existing tests pass (they use `/v1/` paths)

**Risk:** LOW — additive URL patterns only.

---

### Step 2: VersionedSerializerMixin + Standardized Error Handler

**Scope:** Create the mixin that ViewSets use to select v1/v2 serializers based on `request.version`. Create the v2 error exception handler that normalizes all errors to `{error: {code, message, details, field_errors}}`. Neither is wired to real ViewSets yet — tested in isolation.

**Depends on:** Step 1 (versioning active so `request.version` is populated).

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/core/versioning.py` — `VersionedSerializerMixin` |
| CREATE | `src/core/exception_handler.py` — `v2_exception_handler` |
| MODIFY | `src/vtaskforge/settings/base.py` — add `EXCEPTION_HANDLER` to `REST_FRAMEWORK` |
| CREATE | `tests/core/test_versioning_mixin.py` |
| CREATE | `tests/core/test_exception_handler.py` |

**VersionedSerializerMixin design:**
```python
class VersionedSerializerMixin:
    """Mixin for ViewSets that serve both v1 and v2.

    Subclass must define:
        serializer_class = V1Serializer          (existing)
        serializer_class_v2 = V2Serializer        (new)

    Optionally per-action overrides:
        serializer_classes_v2 = {'retrieve': V2DetailSerializer}
    """
    serializer_class_v2 = None
    serializer_classes_v2 = {}

    def get_serializer_class(self):
        if getattr(self.request, 'version', 'v1') == 'v2':
            action_class = self.serializer_classes_v2.get(self.action)
            if action_class:
                return action_class
            if self.serializer_class_v2:
                return self.serializer_class_v2
        return super().get_serializer_class()
```

**Error handler:** Wraps DRF's default exception handler. For v2 requests, normalizes all errors into the standard shape from [v2-api-sdk-DESIGN.md Section 1.5](v2-api-sdk-DESIGN.md). For v1 requests, passes through unchanged.

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_mixin_v1_returns_v1_serializer` | `request.version='v1'` → returns `serializer_class` |
| 2 | `test_mixin_v2_returns_v2_serializer` | `request.version='v2'` → returns `serializer_class_v2` |
| 3 | `test_mixin_v2_action_override` | `request.version='v2'` + action in `serializer_classes_v2` → returns that class |
| 4 | `test_mixin_v2_fallback_when_not_set` | `serializer_class_v2=None` + v2 → falls back to `serializer_class` |
| 5 | `test_error_v2_validation_error` | DRF `ValidationError` → `{error: {code: "VALIDATION_ERROR", field_errors: {...}}}` |
| 6 | `test_error_v2_permission_denied` | `PermissionDenied` → `{error: {code: "PERMISSION_DENIED", message: "..."}}` |
| 7 | `test_error_v2_not_found` | `NotFound` → `{error: {code: "NOT_FOUND"}}` |
| 8 | `test_error_v2_authentication_required` | `NotAuthenticated` → `{error: {code: "AUTHENTICATION_REQUIRED"}}` |
| 9 | `test_error_v2_method_not_allowed` | `MethodNotAllowed` → `{error: {code: "METHOD_NOT_ALLOWED"}}` |
| 10 | `test_error_v2_throttled` | `Throttled` → `{error: {code: "RATE_LIMITED"}}` |
| 11 | `test_error_v1_unchanged` | v1 request errors pass through in original DRF format |
| 12 | `test_error_v2_field_errors_structure` | Nested serializer validation → `field_errors: {"field": ["msg"]}` |
| 13 | `test_error_v2_details_null_when_absent` | Non-validation errors have `details: null, field_errors: null` |

**Regression:**
- [ ] All existing tests pass — v1 error format untouched

**Risk:** MEDIUM — global exception handler affects all requests. v1 passthrough must be exact. The `request.version` check must be the first line of the handler.

---

### Step 3: Ref Serializers + ActorRefField

**Scope:** Create all shared Ref serializers and the `ActorRefField` that resolves User FK → discriminated `{type: "agent"|"user", ...}` shape. Standalone components, tested against model instances. Not wired to ViewSets.

**Depends on:** Nothing (standalone components).

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/core/refs.py` |
| CREATE | `tests/core/test_refs.py` |

**Components:**
- `ProjectRefSerializer(ModelSerializer)` → `{id, name}`
- `WorkplanRefSerializer(ModelSerializer)` → `{id, name}`
- `MilestoneRefSerializer(ModelSerializer)` → `{id, name, status}`
- `TaskRefSerializer(ModelSerializer)` → `{id, title, status}`
- `ActorRefField(serializers.Field)` — given a User FK, checks `Agent.user` OneToOne reverse. Agent user → `{type:"agent", id:agent.id, name:agent.name, pod_name:agent.pod_name}`. Non-agent user → `{type:"user", id:str(user.pk), username:user.username}`. Null FK → `None`.
- `InternalLinkRefField` — polymorphic: resolves `source_type`+`source_id` to the appropriate Ref shape
- `LinkRefField` — polymorphic: internal types get full Ref, external types get `{type, id, label}`

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_project_ref_shape` | `ProjectRefSerializer(project).data == {id, name}` |
| 2 | `test_workplan_ref_shape` | `WorkplanRefSerializer(workplan).data == {id, name}` |
| 3 | `test_milestone_ref_shape` | `MilestoneRefSerializer(milestone).data == {id, name, status}` |
| 4 | `test_task_ref_shape` | `TaskRefSerializer(task).data == {id, title, status}` |
| 5 | `test_actor_ref_agent` | User linked to Agent → `{type:"agent", id, name, pod_name}` |
| 6 | `test_actor_ref_agent_null_pod` | Agent with `pod_name=None` → `pod_name: null` in output |
| 7 | `test_actor_ref_human` | User without Agent → `{type:"user", id, username}` |
| 8 | `test_actor_ref_null` | `None` → `None` |
| 9 | `test_ref_no_extra_fields` | ProjectRef has exactly 2 fields, MilestoneRef exactly 3 |
| 10 | `test_actor_ref_id_is_string` | Agent actor `id` is the agent PK string, user actor `id` is `str(user.pk)` |

**Regression:**
- [ ] All existing tests pass

**Risk:** LOW — pure additive code, no side effects.

---

### Step 4: Permissions Computer

**Scope:** Create the permissions computation module. Given an entity + request user, returns the permissions object. Pure functions tested against model instances.

**Depends on:** Nothing (uses existing `ProjectMembership` and `get_valid_transitions`).

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/core/permissions_computer.py` |
| CREATE | `tests/core/test_permissions_computer.py` |

**Functions:**
- `compute_task_permissions(task, user) → {can_edit, can_delete, available_actions}`
- `compute_project_permissions(project, user) → {can_edit, can_delete, can_archive, can_manage_members}`
- `compute_workplan_permissions(workplan, user) → {can_edit, can_delete, can_archive, can_complete}`
- `compute_milestone_permissions(milestone, user) → {can_edit, can_delete, can_activate, can_complete}`

Logic reuses existing role lookup from `ProjectMembership`: owner=all, member=edit own, viewer=read-only, staff=all. `available_actions` comes from `get_valid_transitions(task.status)` filtered by user role.

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_task_perms_owner` | Owner → `can_edit=True, can_delete=True` |
| 2 | `test_task_perms_member_own` | Member who created → `can_edit=True, can_delete=False` |
| 3 | `test_task_perms_member_other` | Member, didn't create → `can_edit=False, can_delete=False` |
| 4 | `test_task_perms_viewer` | Viewer → all False, `available_actions=[]` |
| 5 | `test_task_perms_staff` | Staff → all True |
| 6 | `test_task_actions_draft` | Draft task owner → includes "todo", "cancelled", "deferred" |
| 7 | `test_task_actions_done` | Done task → `available_actions=[]` (terminal) |
| 8 | `test_task_actions_doing_owner` | Doing task owner → includes "complete", "fail", "block" |
| 9 | `test_project_perms_owner` | Owner → `can_manage_members=True` |
| 10 | `test_project_perms_member` | Member → `can_manage_members=False` |
| 11 | `test_workplan_perms_owner` | Owner → `can_archive=True, can_complete=True` |
| 12 | `test_milestone_perms_active` | Active milestone owner → `can_complete=True` |
| 13 | `test_milestone_perms_pending` | Pending milestone → `can_activate=True, can_complete=False` |
| 14 | `test_no_membership_all_false` | Non-member → all permissions False |

**Regression:**
- [ ] All existing tests pass

**Risk:** LOW — pure computation, no side effects.

---

### Step 5: v2 Serializers — Project, Workplan, Milestone

**Scope:** Create v2 serializers for the three simplest entities. Wire them to ViewSets using `VersionedSerializerMixin`. After this step, `/v2/projects/`, `/v2/workplans/`, `/v2/milestones/` return embedded refs + permissions. v1 unchanged.

**Depends on:** Steps 2, 3, 4.

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/projects/serializers_v2.py` |
| CREATE | `src/workplans/serializers_v2.py` |
| MODIFY | `src/projects/views.py` — add `VersionedSerializerMixin` to `ProjectViewSet` |
| MODIFY | `src/workplans/views.py` — add mixin to `WorkplanViewSet`, `MilestoneViewSet` |
| CREATE | `tests/projects/test_v2_serializers.py` |
| CREATE | `tests/workplans/test_v2_serializers.py` |

**Design notes:**
- Read shape: `owner` and `created_by` become `ActorRef` objects. `project` FK becomes `ProjectRef`. `workplan` FK becomes `WorkplanRef`.
- Write shape: POST/PATCH still accepts bare IDs — the v2 serializer has `ActorRefField` as read-only, writes pass through to the model layer unchanged.
- Permissions: each entity includes the computed `permissions` object from `core/permissions_computer.py`.

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_v2_project_owner_is_actor_ref` | `GET /v2/projects/{id}/` → `owner` is `{type, id, username}` |
| 2 | `test_v2_project_created_by_is_actor_ref` | `created_by` is ActorRef shape |
| 3 | `test_v2_project_has_permissions` | Response includes `permissions` with `can_edit, can_delete, can_archive, can_manage_members` |
| 4 | `test_v1_project_unchanged` | `GET /v1/projects/{id}/` → `owner` is still username string |
| 5 | `test_v2_project_create_returns_v2_shape` | `POST /v2/projects/` → 201 with v2 embedded refs |
| 6 | `test_v2_project_null_owner` | Project without owner → `owner: null` |
| 7 | `test_v2_workplan_project_is_ref` | `GET /v2/workplans/{id}/` → `project` is `{id, name}` |
| 8 | `test_v2_workplan_owner_is_actor_ref` | `owner` is ActorRef |
| 9 | `test_v2_workplan_has_permissions` | Includes `can_edit, can_delete, can_archive, can_complete` |
| 10 | `test_v1_workplan_unchanged` | `GET /v1/workplans/{id}/` → bare project ID |
| 11 | `test_v2_workplan_create_accepts_bare_id` | `POST /v2/workplans/` with `project: "<id>"` → 201 |
| 12 | `test_v2_milestone_workplan_is_ref` | `workplan` is `{id, name}` |
| 13 | `test_v2_milestone_created_by_is_actor_ref` | `created_by` is ActorRef |
| 14 | `test_v2_milestone_has_permissions` | Includes permissions |
| 15 | `test_v2_milestone_create_accepts_bare_id` | `POST /v2/milestones/` with `workplan: "<id>"` → 201 |

**Regression:**
- [ ] All existing tests pass

**E2E:**
- [ ] `curl /v2/projects/` shows embedded ActorRef for owner
- [ ] `curl /v1/projects/` shows username string for owner (unchanged)

**Risk:** MEDIUM — first step touching ViewSets. Must ensure existing `get_serializer_class` overrides compose correctly with the mixin.

---

### Step 6: v2 Serializers — Agent, Review, Note, TaskEvent

**Scope:** Create v2 serializers for Agent, Review, Note, and TaskEvent. Wire to their ViewSets via the mixin.

**Depends on:** Steps 3, 5 (refs exist, mixin pattern established).

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/agents/serializers_v2.py` |
| CREATE | `src/reviews/serializers_v2.py` |
| CREATE | `src/events/serializers_v2.py` |
| CREATE | `src/tasks/serializers_v2.py` — `NoteV2Serializer` (Note v2 lives here alongside Task v2, created in this step, Task v2 added in Step 8) |
| MODIFY | `src/agents/views.py` — add mixin to `AgentViewSet` |
| MODIFY | `src/reviews/views.py` — add mixin to `ReviewViewSet` |
| MODIFY | `src/events/views.py` — add mixin to `TaskEventViewSet` |
| MODIFY | `src/tasks/views.py` — add mixin to `NoteViewSet` |
| CREATE | `tests/agents/test_v2_serializers.py` |
| CREATE | `tests/reviews/test_v2_serializers.py` |
| CREATE | `tests/events/test_v2_serializers.py` |
| CREATE | `tests/tasks/test_v2_note_serializer.py` |

**Key v2 changes:**
- Agent: `current_task` becomes typed `TaskRef` (v1 already returns `{id, title, status}` dict, but v2 uses the shared `TaskRefSerializer`)
- Review: `reviewer_id` (username string) → `reviewer` (ActorRef), `task` (bare ID) → `task` (TaskRef)
- Note: `actor_id` (username string) → `actor` (ActorRef), `task` (bare ID) → `task` (TaskRef)
- TaskEvent: v2 adds `actor` field (ActorRef|null from the actor FK), keeps `trigger_source` as plain string, `task` → TaskRef. Removes legacy `triggered_by` field.

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_v2_agent_current_task_is_task_ref` | `current_task` has `{id, title, status}` shape via `TaskRefSerializer` |
| 2 | `test_v2_agent_current_task_null` | No doing task → `current_task: null` |
| 3 | `test_v1_agent_unchanged` | `GET /v1/agents/` → old shape |
| 4 | `test_v2_review_reviewer_is_actor_ref` | `reviewer` is `{type, id, ...}` |
| 5 | `test_v2_review_task_is_task_ref` | `task` is `{id, title, status}` |
| 6 | `test_v2_review_no_legacy_reviewer_id` | v2 does NOT include `reviewer_id` field |
| 7 | `test_v1_review_still_has_reviewer_id` | v1 unchanged |
| 8 | `test_v2_note_actor_is_actor_ref` | `actor` is ActorRef |
| 9 | `test_v2_note_task_is_task_ref` | `task` is TaskRef |
| 10 | `test_v2_note_no_legacy_actor_id` | v2 does NOT include `actor_id` field |
| 11 | `test_v1_note_still_has_actor_id` | v1 unchanged |
| 12 | `test_v2_event_actor_is_actor_ref` | `actor` field is ActorRef when event has actor FK |
| 13 | `test_v2_event_actor_null_for_system` | System event → `actor: null` |
| 14 | `test_v2_event_trigger_source_is_string` | `trigger_source` remains a plain string |
| 15 | `test_v2_event_task_is_task_ref` | `task` is TaskRef |
| 16 | `test_v1_event_triggered_by_unchanged` | v1 `triggered_by` backward compat still works |

**Regression:**
- [ ] All existing tests pass

**Risk:** LOW — straightforward ref embedding, follows pattern established in Step 5.

---

### Step 7: v2 Serializers — Link (Polymorphic Refs)

**Scope:** Create the v2 Link serializer. Most architecturally complex — `source` and `target` are polymorphic. Replaces N+1 `get_source_title`/`get_target_title` with properly embedded refs. Requires batch prefetch strategy.

**Depends on:** Steps 3, 5 (refs exist, mixin pattern established).

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/links/serializers_v2.py` |
| MODIFY | `src/links/views.py` — add mixin, add batch prefetch in `get_queryset` |
| CREATE | `tests/links/test_v2_serializers.py` |

**v2 shape:**
- `source` → `InternalLinkRef` — `{type:"task", id, title, status}` or `{type:"milestone", id, name, status}` or `{type:"workplan", id, name}`
- `target` → `LinkRef` — internal ref OR `{type:"commit"|"jira"|"doc"|"file"|"area", id, label}` for external references
- `created_by` → ActorRef
- v1 fields `source_type`, `source_id`, `source_title`, `target_type`, `target_id`, `target_title` are replaced by the single `source` and `target` objects

**Prefetch strategy:** ViewSet's `get_queryset` populates serializer context with batch-fetched entities (tasks, milestones, workplans by ID). The serializer reads from context cache instead of issuing per-row queries.

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_v2_link_source_task_ref` | `source_type=task` → `source: {type:"task", id, title, status}` |
| 2 | `test_v2_link_source_milestone_ref` | `source_type=milestone` → `source: {type:"milestone", id, name, status}` |
| 3 | `test_v2_link_source_workplan_ref` | `source_type=workplan` → `source: {type:"workplan", id, name}` |
| 4 | `test_v2_link_target_task_ref` | Internal target type=task → TaskRef shape |
| 5 | `test_v2_link_target_external_commit` | `target_type=commit` → `{type:"commit", id, label}` |
| 6 | `test_v2_link_target_external_jira` | `target_type=jira` → `{type:"jira", id, label}` |
| 7 | `test_v2_link_created_by_actor_ref` | `created_by` is ActorRef |
| 8 | `test_v2_link_no_n_plus_one` | List 10 links → `assertNumQueries` bounded (not 10+ queries) |
| 9 | `test_v2_link_create_accepts_flat_ids` | `POST /v2/links/` with `source_type, source_id, target_type, target_id` → 201 |
| 10 | `test_v2_link_deleted_source_graceful` | Source entity deleted → `source: {type, id, title: null}` |
| 11 | `test_v1_link_unchanged` | v1 still has `source_title`, `target_title` string fields |

**Regression:**
- [ ] All existing tests pass

**Risk:** MEDIUM — polymorphic resolution + batch prefetch is the hardest serializer work in Phase 1.

---

### Step 8: v2 Serializers — Task (Most Complex Entity)

**Scope:** Create the v2 Task serializer. Largest entity with the most ref fields. Also create `TaskDetailV2Serializer` with `?expand=` support that nests v2 serializers for links, reviews, events.

**Depends on:** Steps 2-7 (all refs, permissions computer, mixin, and nested entity v2 serializers must exist).

**Files:**

| Action | Path |
|--------|------|
| MODIFY | `src/tasks/serializers_v2.py` — add `TaskV2Serializer`, `TaskDetailV2Serializer` (file created in Step 6 for Note) |
| MODIFY | `src/tasks/views.py` — add mixin to `TaskViewSet`, wire v2 serializers. Update `MilestoneTasksView` and `ProjectTasksView` to version-select. |
| CREATE | `tests/tasks/test_v2_serializers.py` |

**Key design decisions:**
- **Read shape:** All FK fields become embedded refs: `project` (ProjectRef), `workplan` (WorkplanRef|null), `milestone` (MilestoneRef|null), `requires` (list[TaskRef]), `assigned_to`/`claimed_by`/`created_by` (ActorRef|null)
- **Write shape:** POST/PATCH still accepts bare IDs for `project`, `workplan`, `milestone`, `assigned_to` — same as v1
- **`claimed_by_pod_name` removed** — v2 embeds pod_name inside `claimed_by.pod_name` via ActorRef
- **`permissions.available_actions`** — computed from `get_valid_transitions(task.status)` filtered by user role
- **`TaskDetailV2Serializer`** — extends `TaskV2Serializer` with expand support, using v2 serializers for expanded Link, Review, Event collections
- **Action methods** — all lifecycle actions (`submit`, `claim`, `complete`, etc.) must return v2 shape when accessed via `/v2/`. The mixin handles this automatically via `get_serializer`.

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_v2_task_project_is_ref` | `project` is `{id, name}` |
| 2 | `test_v2_task_workplan_is_ref` | `workplan` is `{id, name}` or `null` |
| 3 | `test_v2_task_milestone_is_ref` | `milestone` is `{id, name, status}` or `null` |
| 4 | `test_v2_task_requires_are_task_refs` | `requires` is list of `{id, title, status}` |
| 5 | `test_v2_task_claimed_by_actor_ref` | `claimed_by` is ActorRef (agent type with pod_name) |
| 6 | `test_v2_task_assigned_to_actor_ref` | `assigned_to` is ActorRef |
| 7 | `test_v2_task_created_by_actor_ref` | `created_by` is ActorRef |
| 8 | `test_v2_task_null_refs` | Unclaimed task → `claimed_by: null, workplan: null, milestone: null` |
| 9 | `test_v2_task_has_permissions` | Response includes `permissions: {can_edit, can_delete, available_actions}` |
| 10 | `test_v2_task_available_actions_draft` | Draft task → `available_actions` includes state machine transitions |
| 11 | `test_v2_task_available_actions_done` | Done task → `available_actions: []` |
| 12 | `test_v2_task_no_claimed_by_pod_name` | v2 does NOT have `claimed_by_pod_name` field |
| 13 | `test_v2_task_create_accepts_bare_ids` | `POST /v2/tasks/` with bare project/workplan/milestone IDs → 201 |
| 14 | `test_v2_task_patch_accepts_bare_ids` | `PATCH /v2/tasks/{id}/` with bare IDs → 200 with v2 shape |
| 15 | `test_v2_task_expand_links_v2` | `GET /v2/tasks/{id}/?expand=links` → links array uses v2 Link shape |
| 16 | `test_v2_task_expand_reviews_v2` | `?expand=reviews` → reviews use v2 Review shape |
| 17 | `test_v2_task_expand_events_v2` | `?expand=events` → events use v2 Event shape |
| 18 | `test_v2_task_actions_return_v2` | `POST /v2/tasks/{id}/submit/` → response is v2 shape |
| 19 | `test_v2_task_claim_returns_v2` | `POST /v2/tasks/{id}/claim/` → v2 shape with ActorRef claimed_by |
| 20 | `test_v1_task_unchanged` | `GET /v1/tasks/{id}/` → `claimed_by` is username string, `project` is bare ID |
| 21 | `test_v2_milestone_tasks_view` | `GET /v2/milestones/{id}/tasks/` → returns v2 task shape |
| 22 | `test_v2_project_tasks_view` | `GET /v2/projects/{id}/backlog/` → returns v2 task shape |

**Regression:**
- [ ] All existing tests pass

**E2E:**
- [ ] Full lifecycle via v2: create task → submit → claim → complete, verify v2 shapes at each step
- [ ] v1 lifecycle still works identically

**Risk:** HIGH — most complex entity, touches the main ViewSet with 15+ action methods. Every action method that calls `get_serializer()` must version-select correctly.

---

### Step 9: v2 Prefs Views — Lock, ChannelMapping, User, Membership, TokenValidation

**Scope:** Add v2 response shapes for prefs APIViews. These are not ViewSets — they need manual version checking via `request.version`. Lock and ChannelMapping get `project` as ProjectRef. User gets `memberships` with ProjectRef. TokenValidation gets `projects` with ProjectRef.

**Depends on:** Steps 3, 5 (refs exist).

**Files:**

| Action | Path |
|--------|------|
| CREATE | `src/prefs/serializers_v2.py` |
| MODIFY | `src/prefs/views.py` — version-select serializers in each APIView |
| CREATE | `tests/prefs/test_v2_serializers.py` |

**v2 changes:**
- `AgentLockSerializer` v2: `user` (username string) → `user` (ActorRef), `project_id` (bare string) → `project` (ProjectRef)
- `ChannelProjectMappingSerializer` v2: `project_id` → `project` (ProjectRef)
- `UserDetailSerializer` v2: `memberships[].project_id` → `memberships[].project` (ProjectRef)
- `TokenValidationView` v2: `projects[].project_id` → `projects[].project` (ProjectRef)
- `ProjectMembershipSerializer` v2: `user_id`+`username` → `user` (ActorRef), `project_id` → `project` (ProjectRef)

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_v2_lock_user_is_actor_ref` | Lock `user` is ActorRef, not username string |
| 2 | `test_v2_lock_project_is_ref` | Lock `project` is `{id, name}`, not bare `project_id` |
| 3 | `test_v1_lock_unchanged` | v1 Lock still has `user: "username"`, `project_id: "..."` |
| 4 | `test_v2_channel_mapping_project_is_ref` | `project` is ProjectRef |
| 5 | `test_v1_channel_mapping_unchanged` | v1 still has `project_id` |
| 6 | `test_v2_token_validate_projects_have_ref` | `projects[].project` is ProjectRef |
| 7 | `test_v1_token_validate_unchanged` | v1 still has `project_id` |
| 8 | `test_v2_user_detail_memberships_have_ref` | `memberships[].project` is ProjectRef, `memberships[].user` is ActorRef |
| 9 | `test_v2_members_list_has_refs` | `GET /v2/projects/{id}/members/` → `user` is ActorRef, `project` is ProjectRef |
| 10 | `test_v1_user_detail_unchanged` | v1 `memberships` still has `project_id`, `user_id`, `username` |

**Regression:**
- [ ] All existing tests pass

**Risk:** LOW — prefs views are simpler, mostly read-only.

---

### Step 10: OpenAPI (drf-spectacular) + Idempotency Middleware + Location Headers

**Scope:** Add `drf-spectacular` for OpenAPI 3.0 schema generation with Swagger UI and Redoc. Add `Idempotency-Key` middleware for v2 POST mutations. Add `Location` header on all v2 201 responses. This is the final infrastructure step.

**Depends on:** Steps 1-9 (all v2 serializers must exist for complete schema generation).

**Files:**

| Action | Path |
|--------|------|
| MODIFY | `requirements/base.txt` — add `drf-spectacular>=0.27` |
| MODIFY | `src/vtaskforge/settings/base.py` — add `drf_spectacular` to `INSTALLED_APPS`, add `SPECTACULAR_SETTINGS`, add idempotency middleware |
| MODIFY | `src/vtaskforge/urls.py` — add `/v2/schema/`, `/v2/schema/swagger-ui/`, `/v2/schema/redoc/` |
| CREATE | `src/core/idempotency.py` — `IdempotencyMiddleware` |
| CREATE | `src/core/location_header.py` — middleware or mixin for 201 Location headers |
| CREATE | `tests/core/test_idempotency.py` |
| CREATE | `tests/core/test_openapi.py` |
| CREATE | `tests/core/test_location_header.py` |

**Idempotency middleware:** On v2 POST with `Idempotency-Key` header, check cache (Redis). If key exists and response is cached, return cached response without processing. If not, process request, cache response keyed by `Idempotency-Key`, return it. Only applies to v2 POST mutations. v1 requests and GET/PATCH/DELETE pass through.

**Location header:** On 201 responses from v2, add `Location: /v2/{resource}/{id}/` header pointing to the created resource's detail URL.

**OpenAPI:** `drf-spectacular` auto-generates the schema from v2 serializers. Endpoints: `/v2/schema/` (JSON), `/v2/schema/swagger-ui/`, `/v2/schema/redoc/`. Schema customization may be needed for discriminated unions (`ActorRef`) and polymorphic types (`LinkRef`).

#### Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_openapi_schema_endpoint` | `GET /v2/schema/` → 200 with valid OpenAPI 3.0 JSON |
| 2 | `test_openapi_swagger_ui` | `GET /v2/schema/swagger-ui/` → 200 |
| 3 | `test_openapi_redoc` | `GET /v2/schema/redoc/` → 200 |
| 4 | `test_openapi_task_schema_has_permissions` | Task component in schema includes `permissions` property |
| 5 | `test_openapi_project_ref_shape` | ProjectRef component has `id` and `name` properties |
| 6 | `test_openapi_actor_ref_discriminated` | ActorRef uses `discriminator` on `type` field |
| 7 | `test_idempotency_duplicate_post` | POST with same `Idempotency-Key` twice → second returns cached 201 without creating duplicate |
| 8 | `test_idempotency_different_key` | POST with different key → processes normally |
| 9 | `test_idempotency_no_header` | POST without `Idempotency-Key` → processes normally (no caching) |
| 10 | `test_idempotency_v1_ignored` | POST to `/v1/` with `Idempotency-Key` → ignored (v1 passthrough) |
| 11 | `test_idempotency_get_ignored` | GET with `Idempotency-Key` → ignored (only POST) |
| 12 | `test_location_header_v2_create` | `POST /v2/tasks/` → 201 with `Location: /v2/tasks/{id}/` header |
| 13 | `test_location_header_v2_project_create` | `POST /v2/projects/` → 201 with `Location` header |
| 14 | `test_location_header_v1_no_change` | `POST /v1/tasks/` → 201 without `Location` header |

**Regression:**
- [ ] All existing tests pass

**E2E:**
- [ ] Swagger UI accessible at `/v2/schema/swagger-ui/` on deployed instance
- [ ] OpenAPI schema validates with an external validator

**Risk:** MEDIUM — drf-spectacular may need schema customization for discriminated unions and polymorphic refs.

---

## 7. Verification Summary

| Step | Scope | New Tests | Risk |
|------|-------|-----------|------|
| 1 | URL routing + versioning | 17 | LOW |
| 2 | VersionedSerializerMixin + error handler | 13 | MEDIUM |
| 3 | Ref serializers + ActorRefField | 10 | LOW |
| 4 | Permissions computer | 14 | LOW |
| 5 | Project / Workplan / Milestone v2 | 15 | MEDIUM |
| 6 | Agent / Review / Note / TaskEvent v2 | 16 | LOW |
| 7 | Link v2 (polymorphic refs) | 11 | MEDIUM |
| 8 | Task v2 (most complex entity) | 22 | HIGH |
| 9 | Prefs v2 (Lock, ChannelMapping, User, etc.) | 10 | LOW |
| 10 | OpenAPI + Idempotency + Location headers | 14 | MEDIUM |
| **Total** | | **142** | |

**Test baseline:** 1497 existing
**Post-Phase 1 target:** ~1639 (1497 + 142 new)

---

## 8. What is NOT in Phase 1

These are explicitly deferred to later phases:

- **Python SDK** (`vtf-sdk-python`) — Phase 2
- **TypeScript SDK** (`@vtf/sdk`, `@vtf/sdk-react`) — Phase 3
- **Consumer migration** (CLI, vafi, MCP, web SPA) — Phase 4
- **v1 deprecation** — Phase 5
- **SSE event payload v2** — deferred until consumer migration (Phase 4d)
- **Cursor pagination changes** — v2 uses the same `VTFCursorPagination` as v1
- **Rate limiting** — mentioned in error taxonomy but not implemented in Phase 1
