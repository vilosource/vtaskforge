# Phase 0: Identity & Authorization — Design

**Date:** 2026-04-03
**Status:** Draft
**Prerequisite for:** v2 API (ActorRef resolution), v2 SDK (typed identity references), `permissions` object

## Problem

vtaskforge stores identity as strings. Every field that should reference a User — `claimed_by`, `created_by`, `owner`, `reviewer_id`, `actor_id`, `triggered_by` — is a `CharField` containing a username or agent ID. There are 13 such fields across 7 models.

This design flaw is the root cause of four cascading problems:

1. **No referential integrity** — nothing prevents writing `claimed_by="nonexistent_user"`. No FK means no database-enforced consistency.
2. **No JOIN path** — displaying "who did this" requires manual string→User lookup per row. The `get_claimed_by_pod_name` SerializerMethodField in `TaskSerializer` does a per-row `Agent.objects.get(id=obj.claimed_by)` — an N+1 query pattern caused directly by the missing FK.
3. **No audit trail** — `created_by` is client-provided and not validated. Any client can claim any identity.
4. **No authorization foundation** — the v2 `permissions` object requires knowing who the user is and what they can access. Without FKs, there's no reliable way to enforce "user X can only see tasks in projects they belong to."

Additionally, the Agent model has **no explicit relationship to User**. The link exists only by convention: `Agent.id` is stored as `User.username` during registration (`agents/views.py:57`). This implicit link cannot be traversed by the ORM.

## Scope

This phase converts all identity fields from CharField to ForeignKey(User), adds an explicit Agent→User link, splits the overloaded `triggered_by` field, and enforces project-scoped authorization on all endpoints.

### Out of Scope

- v2 serializers (Phase 1)
- Python/TypeScript SDKs (Phase 2-3)
- New user management models (ExternalIdentity, SessionRecord, AgentLock, ChannelProjectMapping) — these are already designed with proper FKs in `user-management-DESIGN.md`

---

## Part 1: Identity Field Migration

### 1.1 Complete Field Inventory

Every CharField identity field in the codebase, with its current definition and target:

| # | Model | Field | Current Definition | File:Line | Stores | Target |
|---|-------|-------|--------------------|-----------|--------|--------|
| 1 | Task | `assigned_to` | `CharField(max_length=255, null=True, blank=True, default=None)` | `tasks/models.py:57` | Agent ID (NanoID) | FK User, nullable |
| 2 | Task | `claimed_by` | `CharField(max_length=255, null=True, blank=True, default=None)` | `tasks/models.py:58` | Agent ID (NanoID) | FK User, nullable |
| 3 | Task | `created_by` | `CharField(max_length=255, blank=True, default="")` | `tasks/models.py:62` | Username or agent ID | FK User, nullable |
| 4 | Note | `actor_id` | `CharField(max_length=255)` | `tasks/models.py:81` | Username or agent ID | Rename to `actor`, FK User |
| 5 | Review | `reviewer_id` | `CharField(max_length=255)` | `reviews/models.py:25` | Username or agent ID | Rename to `reviewer`, FK User |
| 6 | TaskEvent | `triggered_by` | `CharField(max_length=255, blank=True, default="")` | `events/models.py:28` | Mixed: agent ID, username, OR action label ("submit", "system") | **Split into two fields** (see 1.3) |
| 7 | Project | `owner` | `CharField(max_length=255, blank=True, default="")` | `projects/models.py:22` | Username | FK User, nullable |
| 8 | Project | `created_by` | `CharField(max_length=255, blank=True, default="")` | `projects/models.py:23` | Username | FK User, nullable |
| 9 | Workplan | `owner` | `CharField(max_length=255, blank=True, default="")` | `workplans/models.py:25` | Username | FK User, nullable |
| 10 | Workplan | `created_by` | `CharField(max_length=255, blank=True, default="")` | `workplans/models.py:30` | Username | FK User, nullable |
| 11 | Milestone | `created_by` | `CharField(max_length=255, blank=True, default="")` | `workplans/models.py:64` | Username | FK User, nullable |
| 12 | Link | `created_by` | `CharField(max_length=255, blank=True, default="")` | `links/models.py:34` | Username | FK User, nullable |

**Total: 12 CharField fields + 1 field to split = 14 field changes across 7 models.**

### 1.2 Agent → User Explicit Link

**Current state:** Agent has no FK to User. The relationship is implicit: `User.objects.get(username=agent.id)` (used in `agents/views.py:44`).

**Target:**

```python
# agents/models.py
class Agent(NanoIDMixin, TimestampMixin):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent",
        null=True,  # Temporarily nullable for migration
    )
    # ... existing fields unchanged
```

**Why OneToOneField, not just convention:**
- Enables `agent.user` and `user.agent` ORM traversal
- `select_related('agent')` works — no manual lookup
- Referential integrity: deleting User cascades to Agent
- The v2 ActorRef serializer can resolve `agent.user` → `UserProfile.user_type` in a single query

**Migration strategy:**
1. Add `user` field as nullable FK
2. Data migration: `Agent.objects.filter(user__isnull=True)` → for each, `agent.user = User.objects.get(username=agent.id)`
3. Remove null=True in a subsequent migration (or keep nullable if agents can be pre-provisioned before User creation)

**Decision: Keep nullable permanently.** Agents may be pre-provisioned by an admin before they register and create a User. The null state means "agent defined but not yet authenticated."

### 1.3 TaskEvent.triggered_by → Split Into Two Fields

**The problem:** `triggered_by` stores two fundamentally different things in the same CharField:

| Current value | What it means | Example call site |
|---------------|---------------|-------------------|
| Agent ID (NanoID) | An agent performed this action | `claim_task()` → `triggered_by=agent_id` |
| `"submit"` | The action name | `views.py:145` → `triggered_by="submit"` |
| `"system"` | Celery background process | `celery_tasks.py:37` → `triggered_by="system"` |
| `"admin"` | Admin force-transition | `views.py:478` → `triggered_by="admin"` |
| `"recover"` | Recovery action | `views.py:311` → `triggered_by="recover"` |
| `""` | Unknown/unset | Default value |

This field conflates **who** (identity) with **what** (action label). Making it a FK to User would lose the action labels. Keeping it a string would lose the identity reference.

**Solution: Split into two fields:**

```python
# events/models.py
class TaskEvent(NanoIDMixin):
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    data = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    # NEW: replaces triggered_by
    trigger_source = models.CharField(max_length=50, blank=True, default="")
    # Action label: "claim", "submit", "complete", "fail", "system", "admin", etc.

    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="task_events",
    )
    # Who triggered this event. null for system/celery events.

    # DEPRECATED: remove after migration
    # triggered_by = models.CharField(...)  — dropped
```

**Migration logic for existing data:**

```python
def forwards(apps, schema_editor):
    TaskEvent = apps.get_model("events", "TaskEvent")
    User = apps.get_model("auth", "User")

    # Build username→User lookup
    user_map = {u.username: u for u in User.objects.all()}

    for event in TaskEvent.objects.all().iterator():
        value = event.triggered_by

        if not value:
            # Empty string → no actor, no trigger source
            event.trigger_source = ""
            event.actor = None
        elif value in ("submit", "system", "admin", "complete", "fail",
                       "recover", "resubmit", "block", "unblock", "defer",
                       "cancel", "unclaim"):
            # Action label → trigger_source only
            event.trigger_source = value
            event.actor = None
        elif value in user_map:
            # Resolvable to a User → both fields
            event.trigger_source = _infer_action(event.event_type)
            event.actor = user_map[value]
        else:
            # Unresolvable → preserve as trigger_source, log warning
            event.trigger_source = value
            event.actor = None
            # Log: f"Unresolvable triggered_by='{value}' on event {event.id}"

        event.save(update_fields=["trigger_source", "actor"])
```

**Callers updated:**

| Call site | Current | After |
|-----------|---------|-------|
| `record_event(task, "claimed", triggered_by=agent_id)` | String agent ID | `record_event(task, "claimed", trigger_source="claim", actor=user)` |
| `perform_transition(task, "doing", triggered_by="submit")` | Action label | `perform_transition(task, "doing", trigger_source="submit", actor=request.user)` |
| `perform_transition(task, ..., triggered_by="system")` | System | `perform_transition(task, ..., trigger_source="system", actor=None)` |
| `perform_transition(task, ..., triggered_by="admin")` | Admin | `perform_transition(task, ..., trigger_source="admin", actor=request.user)` |

### 1.4 Standard FK Pattern for All Identity Fields

All 11 non-TaskEvent identity fields follow one pattern:

```python
field_name = models.ForeignKey(
    User,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="%(app_label)s_%(class)s_field_name",
)
```

**Why `SET_NULL` not `CASCADE`:** Deleting a User should not cascade-delete all their tasks, projects, and workplans. The identity reference is informational — "who created this" — not ownership. The entity survives its creator.

**Why all nullable:** Even fields that were previously `default=""` (non-null) become nullable. Reason: empty string was the "no identity" sentinel. With a FK, `null` is the correct "no identity" value. Existing rows with `created_by=""` map to `created_by=None`.

### 1.5 Data Migration Strategy

**Approach: Two-phase migration per model.**

Phase A (schema): Add new FK fields alongside existing CharFields.
Phase B (data): Populate FK fields from CharField values, then drop CharFields.

This allows rollback: if the data migration fails, the CharFields still have the original data.

**Resolution logic:**

```python
def resolve_identity(value: str) -> User | None:
    """Resolve a CharField identity value to a User instance.

    Both human usernames and agent IDs are stored as User.username
    (agents get User.username = Agent.id on registration), so a
    single lookup covers both cases.
    """
    if not value or value.strip() == "":
        return None

    try:
        return User.objects.get(username=value)
    except User.DoesNotExist:
        logger.warning(f"Unresolvable identity value: '{value}'")
        return None
```

**Unresolvable values:** Set to `None` (null). These represent:
- Values written before User records existed
- Typos or test data
- System identifiers that were never real users

**Migration log:** The data migration writes a log of all unresolvable values and their counts. This is reviewed before dropping the CharField columns.

### 1.6 Field Rename Strategy

Two fields change names to match their semantic role:

| Model | Old Name | New Name | Reason |
|-------|----------|----------|--------|
| Note | `actor_id` | `actor` | It's a FK to User, not a string ID. Django convention: FK fields don't have `_id` suffix (Django adds `_id` automatically for the DB column). |
| Review | `reviewer_id` | `reviewer` | Same reason. The DB column becomes `reviewer_id` automatically. |

**v1 serializer compatibility:** The v1 serializer continues to expose the old field names for backward compatibility during the transition period:

```python
# v1 serializer (kept for backward compat)
class NoteSerializer(serializers.ModelSerializer):
    actor_id = serializers.CharField(source="actor.username", read_only=True)
    # Writes: accept actor_id as string, resolve to User in view/serializer

class ReviewSerializer(serializers.ModelSerializer):
    reviewer_id = serializers.CharField(source="reviewer.username", read_only=True)
```

### 1.7 Model Changes Summary

#### Task (tasks/models.py)

```python
class Task(NanoIDMixin, TimestampMixin):
    # ... existing fields ...

    # CHANGED: CharField → FK User
    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="assigned_tasks",
    )
    claimed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="claimed_tasks",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_tasks",
    )
    # ... rest unchanged ...
```

#### Note (tasks/models.py)

```python
class Note(NanoIDMixin):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="notes")
    text = models.TextField()
    # CHANGED: actor_id CharField → actor FK User
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="task_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

#### Review (reviews/models.py)

```python
class Review(NanoIDMixin, TimestampMixin):
    # ... existing fields ...
    # CHANGED: reviewer_id CharField → reviewer FK User
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviews",
    )
    reviewer_type = models.CharField(max_length=20, default="human")  # kept as-is
```

#### TaskEvent (events/models.py)

```python
class TaskEvent(NanoIDMixin):
    task = models.ForeignKey("tasks.Task", on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES)
    data = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    # CHANGED: triggered_by CharField → split into trigger_source + actor
    trigger_source = models.CharField(max_length=50, blank=True, default="")
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="task_events",
    )
```

#### Project (projects/models.py)

```python
class Project(NanoIDMixin, TimestampMixin):
    # ... existing fields ...
    # CHANGED: CharField → FK User
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_projects",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_projects",
    )
```

#### Workplan (workplans/models.py)

```python
class Workplan(NanoIDMixin, TimestampMixin):
    # ... existing fields ...
    # CHANGED: CharField → FK User
    owner = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_workplans",
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_workplans",
    )
```

#### Milestone (workplans/models.py)

```python
class Milestone(NanoIDMixin, TimestampMixin):
    # ... existing fields ...
    # CHANGED: CharField → FK User
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_milestones",
    )
```

#### Link (links/models.py)

```python
class Link(NanoIDMixin, TimestampMixin):
    # ... existing fields ...
    # CHANGED: CharField → FK User
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_links",
    )
    # NEW: denormalized project_id for authorization scoping (see Part 2)
    project = models.ForeignKey(
        "projects.Project", on_delete=models.PROTECT, null=True, blank=True,
        related_name="links",
    )
    # PROTECT, not CASCADE — consistent with Task→Project (tasks/models.py:31).
    # A project with links cannot be deleted until links are removed.
    # This matches the existing pattern: projects are never silently destroyed.
```

#### Agent (agents/models.py)

```python
class Agent(NanoIDMixin, TimestampMixin):
    # NEW: explicit link to User
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, null=True, blank=True,
        related_name="agent",
    )
    # ... existing fields unchanged ...
```

### 1.8 ProjectScopedModel — Models Know Their Own Project

Every model that belongs to a project must be able to report its own project ID. This is a model-layer concern — the model knows its own relationship to Project. No other layer should need to introspect model structure to figure this out.

```python
# core/mixins.py

class ProjectScopedModel:
    """Protocol for models that belong to a project.

    Each model implements get_project_id() to report its own project.
    The authorization layer calls this method — it never inspects
    model internals directly.

    This follows Open/Closed: adding a new project-scoped model
    requires implementing get_project_id() on that model, not
    modifying the permission classes.
    """

    # ORM filter path from this model to project_id.
    # Used by queryset scoping for list endpoints.
    project_filter_path: str = "project_id"

    def get_project_id(self) -> str | None:
        """Return the project ID this instance belongs to, or None."""
        raise NotImplementedError
```

**Implementation per model:**

```python
# tasks/models.py
class Task(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "project_id"
    def get_project_id(self):
        return self.project_id

class Note(ProjectScopedModel, NanoIDMixin):
    project_filter_path = "task__project_id"
    def get_project_id(self):
        return self.task.project_id if self.task_id else None

# reviews/models.py
class Review(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "task__project_id"
    def get_project_id(self):
        return self.task.project_id if self.task_id else None

# events/models.py
class TaskEvent(ProjectScopedModel, NanoIDMixin):
    project_filter_path = "task__project_id"
    def get_project_id(self):
        return self.task.project_id if self.task_id else None

# projects/models.py
class Project(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "id"
    def get_project_id(self):
        return self.id

# workplans/models.py
class Workplan(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "project_id"
    def get_project_id(self):
        return self.project_id

class Milestone(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "workplan__project_id"
    def get_project_id(self):
        return self.workplan.project_id if self.workplan_id else None

# links/models.py
class Link(ProjectScopedModel, NanoIDMixin, TimestampMixin):
    project_filter_path = "project_id"  # denormalized
    def get_project_id(self):
        return self.project_id
```

**Why this matters:**
- **Open/Closed Principle:** Adding a new project-scoped model means implementing `get_project_id()` on that model. No permission class or utility function needs modification.
- **Single Responsibility:** Each model knows its own structure. The authorization layer asks, it doesn't inspect.
- **No type switching:** The permission layer never uses `hasattr`, `isinstance`, or conditional chains to figure out model relationships.

---

## Part 2: Authorization Enforcement

### 2.1 Design Principles

1. **Models own their project relationship** — via `ProjectScopedModel.get_project_id()`. The authorization layer delegates, never inspects.
2. **Queryset scoping for lists, object permission for detail** — two layers, always both.
3. **Explicit composition over inheritance** — standalone functions called by ViewSets, not mixins that override `get_queryset()`. No MRO surprises.
4. **Create-time authorization lives in `perform_create()`** — each ViewSet knows where the project comes from in its own context (body, URL, parent entity). The generic permission class does not guess.
5. **Staff bypasses all checks** — `is_staff=True` sees everything.
6. **`created_by` is server-set** — never accepted from client input. Always `request.user`.
7. **`owner` is server-set on creation** — defaults to `request.user`, changeable by project owner or staff afterward.

### 2.2 Queryset Scoping — Standalone Function

Every list endpoint must filter to the user's projects. This is a standalone function, not a mixin, to avoid `get_queryset()` MRO collisions with ViewSets that already override it (e.g., `TaskViewSet` has complex filter logic in its `get_queryset()`).

```python
# core/authorization.py

def scope_queryset_to_user_projects(qs, user, model_class):
    """Filter a queryset to only include entities in the user's projects.

    Uses model_class.project_filter_path (from ProjectScopedModel) to
    determine the ORM filter path. Each model defines its own path —
    this function never inspects model structure.

    Args:
        qs: The queryset to filter.
        user: The authenticated user.
        model_class: The model class (must implement ProjectScopedModel).

    Returns:
        Filtered queryset. Staff users get the full queryset.
    """
    if not user.is_authenticated:
        return qs.none()
    if user.is_staff:
        return qs

    filter_path = getattr(model_class, "project_filter_path", None)
    if filter_path is None:
        return qs  # Not project-scoped (e.g., Agent)

    user_project_ids = ProjectMembership.objects.filter(
        user=user
    ).values_list("project_id", flat=True)

    return qs.filter(**{f"{filter_path}__in": user_project_ids})
```

**Usage in each ViewSet** — the ViewSet calls it explicitly in its own `get_queryset()`:

```python
# tasks/views.py
class TaskViewSet(TrackAccessMixin, ModelViewSet):
    def get_queryset(self):
        qs = Task.objects.select_related(
            "project", "milestone", "workplan",
            "assigned_to", "claimed_by", "created_by",
        ).all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Task)
        # ... existing filter logic (status, labels, assigned_to, etc.) ...
        return qs

# workplans/views.py
class MilestoneViewSet(ModelViewSet):
    def get_queryset(self):
        qs = Milestone.objects.select_related(
            "workplan__project", "created_by",
        ).all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Milestone)
        return qs
```

**Why a function, not a mixin:**
- `TaskViewSet.get_queryset()` already has 30+ lines of filter logic, `select_related`, and query param parsing. A mixin's `get_queryset()` + `super()` creates fragile MRO dependency — the scoping must run before filters, but `super()` ordering depends on class declaration order.
- A function call at the top of `get_queryset()` is explicit, readable, and composable. The ViewSet controls the order. No inheritance magic.
- The function reads `model_class.project_filter_path` — it delegates to the model for the ORM path, it doesn't know model internals.

### 2.3 Object-Level Permission — ProjectScopedPermission

For detail views (GET/PATCH/DELETE on a single object), a DRF permission class verifies the object belongs to the user's projects. It calls `obj.get_project_id()` — it never inspects model structure.

```python
# core/authorization.py

class ProjectScopedPermission(BasePermission):
    """Object-level permission: object's project must be in user's memberships.

    Delegates project resolution to the model via get_project_id() — this
    class never inspects model internals.

    Does NOT handle create (POST) — each ViewSet's perform_create() validates
    project membership in its own context (body field, URL param, parent entity).
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        project_id = getattr(obj, "get_project_id", lambda: None)()
        if project_id is None:
            return True  # Not project-scoped (e.g., Agent)

        return ProjectMembership.objects.filter(
            user=request.user, project_id=project_id
        ).exists()
```

**What this class does NOT do:**
- It does NOT handle create (POST). Create-time project validation is context-dependent — the project might come from the request body (`TaskViewSet`), from a URL parameter (`MilestoneTasksView`), or from a parent entity (`BulkImportView`). Trying to handle all of these in a generic permission class leads to hardcoded field name assumptions. Instead, each ViewSet's `perform_create()` validates membership (see 2.6).
- It does NOT resolve `project_id` by inspecting model attributes. It calls `get_project_id()`, which the model implements.

### 2.4 Role-Based Permission — RoleBasedPermission

ProjectMembership has three roles: `owner`, `member`, `viewer`. This permission class enforces role-based write access. It resolves the project via the same `get_project_id()` protocol — no coupling to other permission classes.

| Role | Read | Create | Update | Delete | State Transitions |
|------|------|--------|--------|--------|-------------------|
| owner | Yes | Yes | Yes | Yes | Yes |
| member | Yes | Yes | Yes (own) | No | Yes |
| viewer | Yes | No | No | No | No |

"Own" means: the user created the resource (`created_by == request.user`).

```python
# core/authorization.py

class RoleBasedPermission(BasePermission):
    """Enforce role-based write access within a project.

    Uses obj.get_project_id() to find the project — no coupling to
    other permission classes, no model introspection.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True

        if request.method in SAFE_METHODS:
            return True  # All members can read

        project_id = getattr(obj, "get_project_id", lambda: None)()
        if project_id is None:
            return True

        membership = ProjectMembership.objects.filter(
            user=request.user, project_id=project_id
        ).first()

        if not membership:
            return False

        if membership.role == "owner":
            return True

        if membership.role == "viewer":
            return False

        # member: can create, can update own resources, cannot delete
        if request.method == "DELETE":
            return False

        if request.method in ("PATCH", "PUT"):
            created_by_id = getattr(obj, "created_by_id", None)
            if created_by_id and created_by_id != request.user.id:
                return False

        return True
```

### 2.5 Link Project Denormalization

**Decision: Add `project` FK to Link model.**

Links are polymorphic (source can be task, milestone, or workplan). Without denormalization, resolving the project requires expensive OR queries with subqueries per source type. With a denormalized `project` FK, scoping is a single-field filter.

**How it's set:** On Link creation, the source entity's project is resolved and stored. This logic lives in `links/services.py`, not scattered across views:

```python
# links/services.py
def resolve_link_project(source_type: str, source_id: str) -> Project | None:
    """Resolve the project for a link from its source entity.

    Each source type (task, workplan, milestone) traces to a project
    through its own FK chain. This is the ONE place that knows the
    source→project mapping.
    """
    if source_type == "task":
        return Project.objects.filter(
            tasks__id=source_id
        ).first()
    elif source_type == "workplan":
        return Project.objects.filter(
            workplans__id=source_id
        ).first()
    elif source_type == "milestone":
        return Project.objects.filter(
            workplans__milestones__id=source_id
        ).first()
    return None
```

**Data migration:** Backfill `project` for all existing Links using this same logic.

### 2.6 Create-Time Authorization — In `perform_create()`

Create-time project validation is context-dependent. Each ViewSet/View knows where the project comes from. The pattern is consistent: resolve the project, check membership, set server-controlled fields.

```python
# core/authorization.py

def check_project_membership(user, project_id: str) -> bool:
    """Check if user has membership in the given project. Staff always pass."""
    if user.is_staff:
        return True
    return ProjectMembership.objects.filter(
        user=user, project_id=project_id
    ).exists()

def require_project_membership(user, project_id: str):
    """Raise PermissionDenied if user lacks project membership."""
    if not check_project_membership(user, project_id):
        raise PermissionDenied("You are not a member of this project.")
```

**Per-ViewSet implementation:**

```python
# tasks/views.py — project comes from request body
class TaskViewSet(TrackAccessMixin, ModelViewSet):
    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        require_project_membership(self.request.user, project.id)
        serializer.save(created_by=self.request.user)

# projects/views.py — no project check needed (creating a new project)
class ProjectViewSet(TrackAccessMixin, ModelViewSet):
    def perform_create(self, serializer):
        project = serializer.save(
            owner=self.request.user,
            created_by=self.request.user,
        )
        ProjectMembership.objects.get_or_create(
            user=self.request.user,
            project_id=project.id,
            defaults={"role": "owner"},
        )

# workplans/views.py — project comes from request body
class WorkplanViewSet(ModelViewSet):
    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        require_project_membership(self.request.user, project.id)
        serializer.save(
            owner=self.request.user,
            created_by=self.request.user,
        )

# tasks/views.py — MilestoneTasksView — project comes from URL (milestone)
class MilestoneTasksView(APIView):
    def post(self, request, milestone_id):
        milestone = self.get_milestone(milestone_id)
        if milestone is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        require_project_membership(request.user, milestone.workplan.project_id)
        # ... existing logic, plus: set created_by=request.user ...

# tasks/views.py — ProjectTasksView — project comes from URL
class ProjectTasksView(APIView):
    def post(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        require_project_membership(request.user, project.id)
        # ... existing logic, plus: set created_by=request.user ...

# links/views.py — project resolved from source entity
class LinkViewSet(ModelViewSet):
    def perform_create(self, serializer):
        source_type = serializer.validated_data["source_type"]
        source_id = serializer.validated_data["source_id"]
        project = resolve_link_project(source_type, source_id)
        if project:
            require_project_membership(self.request.user, project.id)
        serializer.save(
            created_by=self.request.user,
            project=project,
        )
```

**Why `perform_create()`, not a generic permission class:**
- Each create endpoint gets its project from a different place: request body, URL parameter, parent entity, or source entity resolution.
- A generic `_check_create()` on a permission class would need to know about all these patterns — it would become a switch statement over view types, violating Open/Closed.
- `perform_create()` is the DRF extension point for this. The ViewSet knows its own context. The authorization utility (`require_project_membership`) is reusable across all of them.

### 2.7 Nested Views and BulkImportView

Three views operate outside the ViewSet pattern and need explicit coverage:

#### MilestoneTasksView (tasks/views.py:515)

Lists and creates tasks under a milestone. Authorization:
- **GET:** Queryset scoped via `scope_queryset_to_user_projects()` before listing
- **POST:** `require_project_membership()` with `milestone.workplan.project_id`
- **Identity:** `created_by=request.user` set on task creation

#### ProjectTasksView (tasks/views.py:561)

Lists and creates backlog tasks under a project. Authorization:
- **GET:** `require_project_membership()` with `project_id` from URL
- **POST:** Same check, plus `created_by=request.user`

#### BulkImportView (core/views.py:17)

Atomically imports workplan + milestones + tasks + links. Authorization:
- Validate `require_project_membership()` for the target project (from `project_id` in payload)
- Set `created_by=request.user` on all created entities (workplan, milestones, tasks)
- Set `owner=request.user` on created workplan
- Set `project` on all created Links via `resolve_link_project()`

**`perform_bulk_import()` updated signature:**

```python
def perform_bulk_import(payload, user: User) -> dict:
    """Create workplan structure atomically.

    Args:
        payload: Import data.
        user: Authenticated user — used to set created_by/owner on all entities.
    """
```

### 2.8 Agent Project Membership

Agents work across projects, but should only access projects they're assigned to.

**Registration flow (updated):**

```python
# agents/views.py — create()
user = User.objects.create_user(username=agent.id)
token = Token.objects.create(user=user)
agent.user = user
agent.save(update_fields=["user"])

# Create profile with user_type=agent
UserProfile.objects.get_or_create(user=user, defaults={"user_type": "agent"})
```

**Project membership — the view orchestrates, the service doesn't cross boundaries:**

`claim_task()` is a domain service in the tasks app — it handles task state transitions, claim validation, and event recording. Creating a ProjectMembership is a cross-cutting concern that belongs to the orchestration layer (the view), not the domain service.

```python
# tasks/views.py — claim action
def claim(self, request, pk=None):
    # ... existing validation ...
    task = claim_task(task_id=pk, agent_id=agent_id, agent_tags=tags)

    # Orchestration: ensure agent has project access (separate from domain logic)
    agent = Agent.objects.select_related("user").get(id=agent_id)
    ProjectMembership.objects.get_or_create(
        user=agent.user,
        project_id=task.project_id,
        defaults={"role": "member"},
    )

    return Response(TaskSerializer(task).data)
```

**Why the view, not the service:**
- `claim_task()` in `tasks/services.py` is a domain service — it validates status, assignment, tags, dependencies, and performs the state transition. These are all task-domain concerns.
- Creating a `ProjectMembership` (prefs app) is an application-level side effect. Putting it in `claim_task()` would make the tasks service depend on the prefs app, violating Dependency Inversion — a lower-level domain module would depend on a higher-level application module.
- The view is the orchestration layer in Django. It composes domain services and handles cross-cutting concerns. This is the correct place.

### 2.9 Auto-Populating Identity on Write

**Principle: The server sets identity fields, never the client.**

| Field | Set When | Set To | Set Where |
|-------|----------|--------|-----------|
| `created_by` | On create (POST) | `request.user` | `perform_create()` in each ViewSet/View |
| `owner` | On create (POST) | `request.user` | `perform_create()` in ProjectViewSet, WorkplanViewSet |
| `claimed_by` | On claim action | Agent's User | `claim_task()` service |
| `assigned_to` | On assign action | Target User | View (resolved from agent ID) |
| Note.`actor` | On create (POST) | `request.user` | `perform_create()` in NoteViewSet |
| Review.`reviewer` | On review submit | `request.user` | `submit_review()` service |
| TaskEvent.`actor` | On event creation | Caller-provided | `record_event()` — passed by the view/service that initiated the action |

**v1 serializer update:** `created_by` and `owner` removed from writable fields:

```python
class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        read_only_fields = ["id", "created_at", "updated_at", "status",
                            "retry_count", "created_by"]  # added created_by
```

### 2.10 ViewSet Permission Configuration

Every ViewSet gets `ProjectScopedPermission` and `RoleBasedPermission`. Queryset scoping is done explicitly in `get_queryset()` via `scope_queryset_to_user_projects()`.

```python
# tasks/views.py
class TaskViewSet(TrackAccessMixin, ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Task.objects.select_related(
            "project", "milestone", "workplan",
            "assigned_to", "claimed_by", "created_by",
        ).all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Task)
        # ... existing filter logic ...
        return qs

# workplans/views.py
class WorkplanViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Workplan.objects.select_related("project", "owner", "created_by").all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Workplan)
        return qs

class MilestoneViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Milestone.objects.select_related("workplan__project", "created_by").all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Milestone)
        return qs

# projects/views.py
class ProjectViewSet(TrackAccessMixin, ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Project.objects.select_related("owner", "created_by").all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Project)
        return qs

# reviews/views.py
class ReviewViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Review.objects.select_related("task__project", "reviewer").all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Review)
        return qs

# events/views.py
class TaskEventViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission]
    # No RoleBasedPermission — events are read-only

    def get_queryset(self):
        qs = TaskEvent.objects.select_related("task__project", "actor").all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, TaskEvent)
        return qs

# links/views.py
class LinkViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Link.objects.select_related("project", "created_by").all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Link)
        return qs

# tasks/views.py
class NoteViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, GenericViewSet):
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_queryset(self):
        qs = Note.objects.select_related("task__project", "actor").filter(
            task_id=self.kwargs["task_id"]
        )
        qs = scope_queryset_to_user_projects(qs, self.request.user, Note)
        return qs
```

**AgentViewSet stays different:** Agent registration is AllowAny (create), IsAuthenticated (others). Agents are not project-scoped — they're a global resource.

### 2.11 Query Optimization — select_related for Identity FKs

Every FK field added is a potential N+1. Each ViewSet's `get_queryset()` must include `select_related` for the new identity FKs. The complete requirements:

| ViewSet | Required `select_related` additions |
|---------|-------------------------------------|
| TaskViewSet | `"assigned_to"`, `"claimed_by"`, `"created_by"` |
| NoteViewSet | `"actor"` |
| ReviewViewSet | `"reviewer"` |
| TaskEventViewSet | `"actor"` |
| ProjectViewSet | `"owner"`, `"created_by"` |
| WorkplanViewSet | `"owner"`, `"created_by"` |
| MilestoneViewSet | `"created_by"` |
| LinkViewSet | `"created_by"`, `"project"` |

For v2 ActorRef resolution (Phase 1), these will need to extend further:

```python
# v2 only — extends to agent profile for pod_name and user_type
"assigned_to__agent",    # AgentActor.pod_name
"claimed_by__agent",     # AgentActor.pod_name
"assigned_to__profile",  # UserProfile.user_type → discriminator
"claimed_by__profile",
"created_by__profile",
```

MCP tools that query models directly (not through serializers) must also add `select_related`:

| MCP tool | Query | Add |
|----------|-------|-----|
| `search.py:48` | `Task.objects.select_related("project", "workplan", "milestone")` | `"assigned_to"`, `"claimed_by"`, `"created_by"` |
| `services.py:294` | `Task.objects.select_related("project", "workplan", "milestone")` | Same |

---

## Part 3: Service Layer Changes

### 3.1 `claim_task()` — Identity by FK

**Current** (`tasks/services.py:159`):

```python
def claim_task(task_id: str, agent_id: str, agent_tags: list = None) -> Task:
    # ...
    task.claimed_by = agent_id  # String
    record_event(task, "claimed", data={"agent_id": agent_id}, triggered_by=agent_id)
```

**After:**

```python
def claim_task(task_id: str, agent_id: str, agent_tags: list = None) -> Task:
    """Domain service: validate and perform a task claim.

    Stays within task-domain boundaries: status checks, assignment checks,
    tag matching, dependency resolution, state transition, event recording.

    Does NOT handle cross-cutting concerns (ProjectMembership) — that is
    the view layer's responsibility (see Part 2.8).
    """
    agent = Agent.objects.select_related("user").get(id=agent_id)

    with transaction.atomic():
        task = Task.objects.select_for_update().get(pk=task_id)
        # ... existing validation (status, assignment, tags, deps) ...

        perform_transition(task, "doing", trigger_source="claim", actor=agent.user)
        task.claimed_by = agent.user  # FK User
        task.claimed_at = timezone.now()
        timeout = task.claim_timeout or timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
        task.claim_expires_at = timezone.now() + timeout
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        record_event(task, "claimed",
            data={"agent_id": agent_id},
            trigger_source="claim",
            actor=agent.user,
        )

    return task
```

**Note:** `claim_task()` does not create `ProjectMembership`. That is handled by the view (see Part 2.8). The service stays within the tasks domain — it depends on `agents.models.Agent` (to resolve the user) and `events.services.record_event` (existing dependency), but not on `prefs.models.ProjectMembership`.

### 3.2 `perform_transition()` — Accepts Actor

**Current** (`tasks/state_machine.py:136`):

```python
def perform_transition(task, new_status: str, triggered_by: str = ""):
    # ...
    record_event(task, "status_changed", data={...}, triggered_by=triggered_by)
```

**After:**

```python
def perform_transition(task, new_status: str, trigger_source: str = "", actor: User = None):
    validate_transition(task, new_status)
    _run_guards(task, task.status, new_status)
    old_status = task.status
    task.status = new_status
    task.save(update_fields=["status", "updated_at"])
    record_event(task, "status_changed",
        data={"from": old_status, "to": new_status},
        trigger_source=trigger_source,
        actor=actor,
    )
```

### 3.3 `record_event()` — New Signature

**Current** (`events/services.py:4`):

```python
def record_event(task, event_type: str, data: dict = None, triggered_by: str = "") -> TaskEvent | None:
```

**After:**

```python
def record_event(task, event_type: str, data: dict = None,
                 trigger_source: str = "", actor: User = None) -> TaskEvent | None:
    try:
        return TaskEvent.objects.create(
            task=task,
            event_type=event_type,
            data=data if data is not None else {},
            trigger_source=trigger_source,
            actor=actor,
        )
    except Exception:
        return None
```

### 3.4 `submit_review()` — Accepts User

**Current** (`reviews/services.py:22`):

```python
def submit_review(task_id, decision, reason="", reviewer_id="", reviewer_type="human"):
    # ...
    Review.objects.create(reviewer_id=reviewer_id, ...)
    record_event(task, ..., triggered_by=reviewer_id)
```

**After:**

```python
def submit_review(task_id, decision, reason="", reviewer: User = None, reviewer_type="human"):
    # ...
    Review.objects.create(reviewer=reviewer, ...)
    record_event(task, ..., trigger_source="review", actor=reviewer)
```

---

## Part 4: v1 Serializer Backward Compatibility

v1 serializers must continue working during the v2 development period. FK fields need to serialize as strings (the old format) for v1 consumers.

### 4.1 Read (Response)

FK fields serialize as the username/ID string, same as before:

```python
class TaskSerializer(serializers.ModelSerializer):
    # FK fields exposed as strings for v1 backward compat
    assigned_to = serializers.SlugRelatedField(
        slug_field="username", queryset=User.objects.all(),
        required=False, allow_null=True,
    )
    claimed_by = serializers.SlugRelatedField(
        slug_field="username", read_only=True, allow_null=True,
    )
    created_by = serializers.SlugRelatedField(
        slug_field="username", read_only=True, allow_null=True,
    )
```

**Output:** `"claimed_by": "executor-1"` — same string format as before.

### 4.2 Write (Request)

For fields that accept writes (like `assigned_to`), `SlugRelatedField` resolves the username string to a User instance automatically. Fields that are server-set (`created_by`, `claimed_by`) are read-only.

### 4.3 Renamed Fields

For Note (`actor_id` → `actor`) and Review (`reviewer_id` → `reviewer`):

```python
class NoteSerializer(serializers.ModelSerializer):
    actor_id = serializers.SlugRelatedField(
        source="actor", slug_field="username", read_only=True, allow_null=True,
    )
    class Meta:
        model = Note
        fields = ["id", "task", "text", "actor_id", "created_at"]  # Keep old field name

class ReviewSerializer(serializers.ModelSerializer):
    reviewer_id = serializers.SlugRelatedField(
        source="reviewer", slug_field="username", read_only=True, allow_null=True,
    )
```

### 4.4 TaskEvent Compatibility

```python
class TaskEventSerializer(serializers.ModelSerializer):
    triggered_by = serializers.SerializerMethodField()  # Combine back to string for v1

    def get_triggered_by(self, obj):
        """v1 compat: return the old triggered_by format."""
        if obj.actor:
            return obj.actor.username
        return obj.trigger_source

    class Meta:
        model = TaskEvent
        fields = ["id", "task", "event_type", "data", "timestamp", "triggered_by"]
```

---

## Part 5: MCP Server Changes

The MCP tools use identity fields directly. All callers must be updated:

| File | Current Pattern | After |
|------|----------------|-------|
| `mcp_server/tools/search.py:89` | `"claimed_by": task.claimed_by` | `"claimed_by": task.claimed_by.username if task.claimed_by else None` |
| `mcp_server/tools/detail.py:57` | `task_info.get("claimed_by")` | Use serializer output (unchanged if v1 compat works) |
| `mcp_server/tools/manage.py:670` | `task.assigned_to = assigned_to` (string) | `task.assigned_to = User.objects.get(username=assigned_to)` |
| `mcp_server/tools/_workflow_agent.py:247` | `actor = agent_id or task.claimed_by or ""` | `actor = agent_user or task.claimed_by` (User instance) |
| `mcp_server/tools/_review_agent.py:51` | `task.claimed_by` string comparison | `task.claimed_by.username` for comparison, `task.claimed_by` (User) for review submission |

### 5.1 SSE Event Broadcasting

The SSE system broadcasts task changes to connected clients. After the FK migration, the broadcaster must `select_related("actor")` when loading TaskEvents for serialization, or the v1 compat `get_triggered_by()` method will cause N+1 queries.

Any SSE publisher that reads TaskEvent records must update its queryset:

```python
# Before
events = TaskEvent.objects.filter(task=task).order_by("-timestamp")[:20]

# After
events = TaskEvent.objects.select_related("actor").filter(task=task).order_by("-timestamp")[:20]
```

---

## Part 6: Migration Sequence

Ordered to minimize risk. Each step is independently deployable.

### Step 1: Agent.user FK + Data Migration

1. Add `Agent.user` OneToOneField (nullable)
2. Data migration: link existing Agents to Users via `User.objects.get(username=agent.id)`
3. Update `agents/views.py` create: set `agent.user = user` on registration
4. Update `agents/views.py` upsert: set `agent.user = user` on re-registration
5. Tests: verify Agent.user is set on create and upsert

**Risk: Low.** Additive change, no existing fields modified.

### Step 2: TaskEvent.triggered_by → trigger_source + actor

1. Add `trigger_source` and `actor` fields to TaskEvent
2. Data migration: split existing `triggered_by` values
3. Update `record_event()` signature
4. Update `perform_transition()` signature
5. Update all callers (views, services, celery_tasks, MCP tools)
6. Update v1 serializer with `get_triggered_by` compat method
7. Drop `triggered_by` column
8. Tests: verify events record both trigger_source and actor

**Risk: Medium.** Many callers, but the signature change is mechanical.

### Step 3: Task identity fields (assigned_to, claimed_by, created_by)

1. Add FK fields alongside CharFields (temporary dual-write)
2. Data migration: populate FKs from CharFields
3. Update `claim_task()` service to set FK
4. Update views to set FK on assign/unassign
5. Update serializer to use SlugRelatedField
6. Drop CharFields
7. Tests: verify claim, assign, create all set FK correctly

**Risk: High.** Task is the most-used model. `claim_task()` is the hot path.

### Step 4: Note.actor_id → actor, Review.reviewer_id → reviewer

1. Add FK fields
2. Data migration
3. Update views and services
4. Update serializers (field rename compat)
5. Drop CharFields
6. Tests

**Risk: Low-Medium.** Fewer callers, well-scoped.

### Step 5: Project/Workplan/Milestone identity fields

1. Add FK fields to Project (owner, created_by), Workplan (owner, created_by), Milestone (created_by)
2. Data migration
3. Update `perform_create()` in views to set from `request.user`
4. Make `created_by`/`owner` read-only in v1 serializers
5. Drop CharFields
6. Tests

**Risk: Medium.** Must ensure `owner` is set on project creation.

### Step 6: Link.created_by FK + Link.project denormalization

1. Add `created_by` FK and `project` FK to Link
2. Data migration: resolve created_by, backfill project from source entity
3. Update LinkViewSet: add `scope_queryset_to_user_projects()` call and `ProjectScopedPermission`
4. Update link creation to auto-set project
5. Drop CharField
6. Tests

**Risk: Medium.** Polymorphic source resolution needs careful testing.

### Step 7: Authorization enforcement

1. **Bootstrap migration: create ProjectMembership for all existing users.** Without this, deploying authorization enforcement locks every non-staff user out of every endpoint immediately. The migration creates memberships from existing activity:

```python
def bootstrap_project_memberships(apps, schema_editor):
    """Create ProjectMembership records for all users with existing activity.

    Any user who created, owns, claimed, or was assigned to a resource
    in a project gets a membership. Project creators get 'owner' role,
    all others get 'member'.
    """
    User = apps.get_model("auth", "User")
    Project = apps.get_model("projects", "Project")
    Task = apps.get_model("tasks", "Task")
    Workplan = apps.get_model("workplans", "Workplan")
    ProjectMembership = apps.get_model("prefs", "ProjectMembership")

    for project in Project.objects.all():
        # Collect all users with activity in this project
        user_ids = set()

        # Project owner and creator
        if project.owner_id:
            user_ids.add(project.owner_id)
        if project.created_by_id:
            user_ids.add(project.created_by_id)

        # Task participants
        task_user_fields = Task.objects.filter(project=project).values_list(
            "created_by_id", "claimed_by_id", "assigned_to_id",
        )
        for created, claimed, assigned in task_user_fields:
            if created: user_ids.add(created)
            if claimed: user_ids.add(claimed)
            if assigned: user_ids.add(assigned)

        # Workplan owners/creators
        wp_user_fields = Workplan.objects.filter(project=project).values_list(
            "owner_id", "created_by_id",
        )
        for owner, created in wp_user_fields:
            if owner: user_ids.add(owner)
            if created: user_ids.add(created)

        # Create memberships (skip existing)
        for user_id in user_ids:
            role = "owner" if user_id == project.owner_id else "member"
            ProjectMembership.objects.get_or_create(
                user_id=user_id,
                project_id=project.id,
                defaults={"role": role},
            )
```

2. Add `scope_queryset_to_user_projects()`, `ProjectScopedPermission`, `RoleBasedPermission`, `require_project_membership()`, `check_project_membership()` to `core/authorization.py`
3. Add `ProjectScopedModel` mixin to `core/mixins.py`
4. Add `get_project_id()` and `project_filter_path` to all project-scoped models
5. Apply authorization to all ViewSets (see 2.10)
6. Apply authorization to nested views: MilestoneTasksView, ProjectTasksView (see 2.7)
7. Update BulkImportView to accept `user` param and validate membership (see 2.7)
8. Add agent auto-membership in claim view (see 2.8)
9. Tests: verify non-member gets 403, member gets 200, viewer gets read-only
10. Tests: verify bootstrap migration created correct memberships
11. Full regression: verify 1413 existing tests still pass (most tests create users that need memberships — test factories must be updated to create memberships alongside projects)

**Risk: High.** This changes access control for every endpoint. The bootstrap migration is critical — without it, the system is unusable after deployment. Test factories must be updated to create ProjectMembership records, or nearly all existing tests will fail with 403.

---

## Part 7: Verification Process

This section is the authoritative reference for how each step is verified. Every step follows this process exactly. No step is done until every criterion is met.

### 7.1 Three Test Tiers

| Tier | What it proves | How to run | Blocks? |
|------|---------------|------------|---------|
| **TDD (Red→Green)** | Individual behavior works in isolation | `pytest tests/ -v` (default test DB, eager Celery) | Blocks commit |
| **Integration** | Migrations apply, querysets work against real Postgres, serializers produce correct shapes | `DATABASE_URL=postgres://vtf:vtfdev@localhost:5436/vtaskforge pytest tests/ -v` with `docker compose up -d db` | Blocks image build |
| **E2E** | Full HTTP request→response through the deployed stack, REST and MCP channels | `pytest tests/e2e/ -v` against docker-compose.e2e.yml or test environment | Blocks declaring step done |

All three tiers must pass. Skipping a tier is not allowed.

### 7.2 Step Execution Process

Every step follows this exact sequence. Do not skip or reorder.

```
1. WRITE TDD TESTS (RED)
   - Write all new test functions for this step
   - Run them: they must ALL FAIL (red)
   - If any pass before implementation, the test is wrong

2. IMPLEMENT
   - Model changes + migration
   - Service/view changes
   - Serializer changes
   - Factory/fixture updates

3. TDD TESTS (GREEN)
   - Run the new tests: they must ALL PASS
   - If any fail, fix the implementation (not the test)

4. FULL REGRESSION
   - Run: pytest tests/ -q --tb=short
   - ALL existing tests must pass (currently 1413)
   - If tests fail, fix factories/fixtures, not the tests' intent
   - Do NOT delete or skip failing tests

5. INTEGRATION VERIFICATION
   - Start Postgres: docker compose up -d db
   - Run migrations: DATABASE_URL=... python src/manage.py migrate
   - Verify: DATABASE_URL=... pytest tests/ -q --tb=short
   - Verify migration applies cleanly to existing data

6. BUILD + DEPLOY TO TEST
   - Build image: docker build -f Dockerfile.prod -t harbor.viloforge.com/vafi/vtf:$(git rev-parse --short HEAD) .
   - Push: docker push harbor.viloforge.com/vafi/vtf:<hash>
   - Deploy: kubectl set image deployment/vtf-api -n vtf-dev vtf-api=harbor.viloforge.com/vafi/vtf:<hash>
   - Run migration in pod: kubectl exec deployment/vtf-api -n vtf-dev -- python src/manage.py migrate

7. E2E VERIFICATION
   - Run E2E suite against deployed stack
   - Each step has specific E2E verification criteria (see 7.4)
   - If E2E fails, diagnose on deployed stack — do not assume unit tests cover it

8. DEFINITION OF DONE REVIEW
   - Walk through every DoD item for this step (see 7.4)
   - Check each one: pass or fail
   - ALL must pass. If any fail, go back to step 2
   - Only after all pass: commit, journal, move to next step
```

### 7.3 Test Infrastructure Changes (Before Step 1)

Before any step begins, the test factories and fixtures must be prepared for the transition. These changes are made as a prerequisite commit.

#### Factory Updates

The following factories currently use string identity values that will become FKs:

| Factory | Field | Current Value | After |
|---------|-------|--------------|-------|
| `NoteFactory` | `actor_id` | `"test-actor"` | `actor` = `LazyAttribute` → User instance (Step 4) |
| `ReviewFactory` | `reviewer_id` | `"test-reviewer"` | `reviewer` = `LazyAttribute` → User instance (Step 4) |
| `TaskEventFactory` | (no triggered_by) | N/A | Add `trigger_source`, `actor` fields (Step 2) |

The `doing_task` fixture in `conftest.py` sets `claimed_by="agent-1"` — this must change to a User FK in Step 3.

**Strategy:** Update each factory in the same step that migrates its model. Do not update factories ahead of their step — the old factories must work until the model changes.

#### Membership-Aware Factories (Step 7 Only)

When Step 7 enables authorization enforcement, test factories must create ProjectMembership records or tests will get 403. This is handled by:

1. A test helper function:

```python
# tests/helpers.py
def as_project_member(user, project, role="member"):
    """Ensure user has membership in project. Idempotent."""
    from prefs.models import ProjectMembership
    ProjectMembership.objects.get_or_create(
        user=user, project_id=project.id, defaults={"role": role}
    )
```

2. Updated `api_client` fixture in `conftest.py` — the staff user (`is_staff=True`) bypasses authorization, so most existing tests continue working. Tests that use non-staff users must call `as_project_member()`.

3. `ProjectFactory` gains a post-generation hook:

```python
@factory.post_generation
def members(self, create, extracted, **kwargs):
    """Auto-create owner membership for the project creator."""
    if not create:
        return
    if self.owner_id:
        from prefs.models import ProjectMembership
        ProjectMembership.objects.get_or_create(
            user_id=self.owner_id,
            project_id=self.id,
            defaults={"role": "owner"},
        )
```

### 7.4 Definition of Done — Per Step

Each step has a concrete, checkable list. Every item must be verified. "Done" means ALL items pass.

---

#### Step 1: Agent.user FK — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_agent_create_links_user` | POST /v1/agents/ → `agent.user` is User with `username == agent.id` |
| 2 | `test_agent_upsert_preserves_user` | Re-register same agent → `agent.user` unchanged, no orphan Users |
| 3 | `test_agent_user_reverse_lookup` | `user.agent` returns the Agent instance |
| 4 | `test_agent_user_cascade_delete` | Delete User → Agent is deleted (CASCADE) |
| 5 | `test_data_migration_backfills_user` | Existing agents without FK get backfilled from User.username match |
| 6 | `test_agent_without_user_allowed` | Agent(user=None) is valid (nullable for pre-provisioning) |

**Integration:**
- [ ] Migration applies cleanly on real Postgres: `makemigrations --check` finds nothing new
- [ ] Data migration runs without errors on existing agents

**E2E:**
- [ ] Register agent via REST API → query database → `Agent.user_id` is not null
- [ ] Re-register agent → token unchanged, `Agent.user_id` still correct

**Regression:**
- [ ] Full test suite passes (0 failures)
- [ ] `AgentFactory` updated: creates User + sets `agent.user` in post-generation

---

#### Step 2: TaskEvent Split — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_record_event_with_actor` | `record_event(task, "claimed", trigger_source="claim", actor=user)` → event.actor == user, event.trigger_source == "claim" |
| 2 | `test_record_event_system_no_actor` | `record_event(task, "status_changed", trigger_source="system")` → event.actor is None |
| 3 | `test_perform_transition_passes_actor` | `perform_transition(task, "doing", trigger_source="claim", actor=user)` → resulting event has both fields |
| 4 | `test_v1_serializer_compat_actor` | Event with actor → serializer returns `triggered_by: "username"` |
| 5 | `test_v1_serializer_compat_system` | Event without actor → serializer returns `triggered_by: "system"` |
| 6 | `test_data_migration_agent_id_resolves` | Existing event with `triggered_by=agent_nanoid` → `actor` = User, `trigger_source` inferred from event_type |
| 7 | `test_data_migration_action_label_preserved` | Existing event with `triggered_by="submit"` → `trigger_source="submit"`, `actor=None` |
| 8 | `test_data_migration_empty_string` | Existing event with `triggered_by=""` → both fields empty/null |
| 9 | `test_celery_expire_claims_uses_new_signature` | `expire_stale_claims()` → events created with `trigger_source="system"`, `actor=None` |

**Integration:**
- [ ] Migration applies cleanly
- [ ] Data migration correctly splits ALL existing events (spot-check counts: events with actor vs. without)
- [ ] No `triggered_by` column remains after migration

**E2E:**
- [ ] Claim a task → GET /v1/tasks/{id}/?expand=events → latest event has `triggered_by` field (v1 compat) with agent username
- [ ] Wait for claim expiry (or force via Celery) → event with `triggered_by: "system"`

**Regression:**
- [ ] Full test suite passes
- [ ] ALL callers updated: `tasks/views.py`, `tasks/services.py`, `tasks/celery_tasks.py`, `reviews/services.py`, `mcp_server/tools/_workflow_agent.py`, `mcp_server/tools/_review_agent.py`, `mcp_server/tools/manage.py`
- [ ] `TaskEventFactory` updated with `trigger_source` and `actor` fields

---

#### Step 3: Task Identity Fields — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_claim_sets_user_fk` | `claim_task(task_id, agent_id)` → `task.claimed_by` is User instance |
| 2 | `test_assign_sets_user_fk` | Assign action → `task.assigned_to` is User instance |
| 3 | `test_unassign_clears_fk` | Unassign → `task.assigned_to` is None |
| 4 | `test_create_sets_created_by` | POST /v1/tasks/ → `task.created_by == request.user` |
| 5 | `test_created_by_not_writable` | POST /v1/tasks/ with `created_by: "hacker"` → field ignored, set to request.user |
| 6 | `test_v1_read_claimed_by_string` | GET /v1/tasks/{id}/ → `claimed_by` is username string |
| 7 | `test_v1_read_assigned_to_string` | GET /v1/tasks/{id}/ → `assigned_to` is username string |
| 8 | `test_v1_write_assigned_to_resolves` | PATCH with `assigned_to: "agent-name"` → resolves to User |
| 9 | `test_claimed_by_null_serializes_null` | Task with no claim → `claimed_by: null` |
| 10 | `test_select_related_no_n_plus_1` | List tasks → assert num queries does not scale with result count |
| 11 | `test_data_migration_populates_fks` | Existing tasks with string claimed_by → FK populated |
| 12 | `test_data_migration_unresolvable_null` | Existing task with `claimed_by="nonexistent"` → FK set to null |

**Integration:**
- [ ] Migration applies cleanly
- [ ] Data migration resolves existing string values to Users
- [ ] Migration log reports unresolvable values (if any)

**E2E:**
- [ ] Full lifecycle: create task → submit → claim → complete
- [ ] At each step, GET task → verify identity fields are correct username strings (v1 compat)
- [ ] Verify `claimed_by_pod_name` still works (now via Agent.user FK → Agent reverse lookup)

**Regression:**
- [ ] Full test suite passes
- [ ] `conftest.py` `doing_task` fixture updated: `claimed_by` = User instance (not string)
- [ ] All tests that create tasks with `claimed_by`/`assigned_to`/`created_by` strings updated

---

#### Step 4: Note + Review Renames — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_note_create_sets_actor` | POST note → `note.actor == request.user` |
| 2 | `test_note_actor_not_writable` | POST note with `actor_id: "hacker"` → ignored, set to request.user |
| 3 | `test_review_submit_sets_reviewer` | Submit review → `review.reviewer == request.user` |
| 4 | `test_v1_note_serializer_actor_id` | GET note → response has `actor_id` field with username string |
| 5 | `test_v1_review_serializer_reviewer_id` | GET review → response has `reviewer_id` field with username string |
| 6 | `test_data_migration_notes` | Existing notes with string actor_id → FK populated |
| 7 | `test_data_migration_reviews` | Existing reviews with string reviewer_id → FK populated |

**Integration:**
- [ ] Migration applies cleanly, DB column renamed (`actor_id` stays as column name for Note.actor FK, `reviewer_id` stays as column name for Review.reviewer FK — Django convention)

**E2E:**
- [ ] Add note to task → GET task with ?expand=events → note has `actor_id` in response
- [ ] Submit review → GET reviews → review has `reviewer_id` in response

**Regression:**
- [ ] Full test suite passes
- [ ] `NoteFactory` updated: `actor` = User instance (not `actor_id` string)
- [ ] `ReviewFactory` updated: `reviewer` = User instance (not `reviewer_id` string)

---

#### Step 5: Project/Workplan/Milestone Identity Fields — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_project_create_sets_owner` | POST /v1/projects/ → `project.owner == request.user` |
| 2 | `test_project_create_sets_created_by` | POST /v1/projects/ → `project.created_by == request.user` |
| 3 | `test_workplan_create_sets_owner_created_by` | POST workplan → both set to request.user |
| 4 | `test_milestone_create_sets_created_by` | POST milestone → created_by set to request.user |
| 5 | `test_owner_read_only_v1` | PATCH project with `owner: "someone"` → ignored |
| 6 | `test_created_by_read_only_v1` | PATCH project with `created_by: "someone"` → ignored |
| 7 | `test_v1_serializer_owner_string` | GET /v1/projects/{id}/ → `owner` is username string |
| 8 | `test_data_migration_projects` | Existing projects with string owner/created_by → FKs populated |
| 9 | `test_data_migration_workplans` | Existing workplans → FKs populated |
| 10 | `test_data_migration_milestones` | Existing milestones → FKs populated |

**Integration:**
- [ ] Migration applies cleanly
- [ ] Data migration resolves all existing values

**E2E:**
- [ ] Create project → GET → owner and created_by are username strings
- [ ] Create workplan → verify same

**Regression:**
- [ ] Full test suite passes
- [ ] `ProjectFactory`, `WorkplanFactory`, `MilestoneFactory` optionally accept `owner`/`created_by` as User

---

#### Step 6: Link Identity + Project Denormalization — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_link_create_sets_created_by` | POST link → `link.created_by == request.user` |
| 2 | `test_link_project_from_task_source` | Link with source_type=task → `link.project == task.project` |
| 3 | `test_link_project_from_workplan_source` | Link with source_type=workplan → `link.project == workplan.project` |
| 4 | `test_link_project_from_milestone_source` | Link with source_type=milestone → `link.project == milestone.workplan.project` |
| 5 | `test_link_project_scoping` | User in project A, not B → listing links returns only project A links |
| 6 | `test_data_migration_backfills_project` | Existing links get project populated from source entity |

**Integration:**
- [ ] Migration applies cleanly
- [ ] Data migration backfills project for ALL existing links

**E2E:**
- [ ] Create link → GET → verify `created_by` in response
- [ ] Verify link appears in project-scoped queries

**Regression:**
- [ ] Full test suite passes
- [ ] `LinkFactory` updated with `created_by` (User) and `project` fields

---

#### Step 7: Authorization Enforcement — Definition of Done

**TDD tests (new):**

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_non_member_403_task_list` | User not in project → GET /v1/tasks/ returns 0 tasks (scoped) |
| 2 | `test_non_member_403_task_detail` | User not in project → GET /v1/tasks/{id}/ → 403 |
| 3 | `test_member_sees_own_project_tasks` | User in project A → sees A's tasks, not B's |
| 4 | `test_staff_sees_all_tasks` | Staff user → sees all tasks across all projects |
| 5 | `test_viewer_can_read` | Viewer role → GET → 200 |
| 6 | `test_viewer_cannot_create` | Viewer → POST /v1/tasks/ → 403 |
| 7 | `test_viewer_cannot_update` | Viewer → PATCH /v1/tasks/{id}/ → 403 |
| 8 | `test_member_can_create` | Member → POST /v1/tasks/ → 201 |
| 9 | `test_member_can_update_own` | Member → PATCH own task → 200 |
| 10 | `test_member_cannot_update_others` | Member → PATCH another's task → 403 |
| 11 | `test_member_cannot_delete` | Member → DELETE → 403 |
| 12 | `test_owner_can_delete` | Owner → DELETE → 200/204 |
| 13 | `test_create_validates_project_membership` | Non-member → POST /v1/tasks/ with foreign project → 403 |
| 14 | `test_milestone_tasks_view_checks_membership` | Non-member → POST to /v1/milestones/{id}/tasks/ → 403 |
| 15 | `test_project_tasks_view_checks_membership` | Non-member → POST to /v1/projects/{id}/tasks/ → 403 |
| 16 | `test_bulk_import_checks_membership` | Non-member → POST /v1/bulk/import → 403 |
| 17 | `test_claim_creates_agent_membership` | After claim → agent User has ProjectMembership |
| 18 | `test_claim_existing_membership_no_duplicate` | Agent already member → claim doesn't create duplicate |
| 19 | `test_queryset_scoping_workplans` | Non-member → GET /v1/workplans/ returns 0 for foreign project |
| 20 | `test_queryset_scoping_milestones` | Same for milestones |
| 21 | `test_queryset_scoping_reviews` | Same for reviews |
| 22 | `test_queryset_scoping_events` | Same for events |
| 23 | `test_queryset_scoping_links` | Same for links |
| 24 | `test_queryset_scoping_notes` | Same for notes |
| 25 | `test_project_scoped_model_task` | `task.get_project_id() == task.project_id` |
| 26 | `test_project_scoped_model_milestone` | `milestone.get_project_id() == milestone.workplan.project_id` |
| 27 | `test_project_scoped_model_review` | `review.get_project_id() == review.task.project_id` |
| 28 | `test_project_scoped_model_note` | `note.get_project_id() == note.task.project_id` |
| 29 | `test_project_scoped_model_event` | `event.get_project_id() == event.task.project_id` |
| 30 | `test_project_scoped_model_link` | `link.get_project_id() == link.project_id` |
| 31 | `test_bootstrap_migration_owner` | Project owner → 'owner' membership after bootstrap |
| 32 | `test_bootstrap_migration_claimers` | Task claimers → 'member' membership after bootstrap |
| 33 | `test_bootstrap_migration_no_activity` | User with no project activity → no membership |

**Integration:**
- [ ] Bootstrap migration runs on real Postgres without errors
- [ ] Membership counts match expected activity-based population
- [ ] All existing API tests pass with authorization enabled

**E2E (new scenarios required — non-staff users):**
- [ ] Create non-staff user + token via seed script
- [ ] Create two projects, user is member of project A only
- [ ] GET /v1/tasks/ → returns only project A tasks
- [ ] GET /v1/tasks/{project-B-task-id}/ → 403
- [ ] POST /v1/tasks/ with project B → 403
- [ ] POST /v1/tasks/ with project A → 201
- [ ] Create viewer user → verify read-only behavior via REST
- [ ] Agent claims task → verify agent gets ProjectMembership

**Regression:**
- [ ] Full test suite passes
- [ ] `conftest.py` `api_client` fixture: staff user (bypasses auth) — existing tests unaffected
- [ ] `ProjectFactory` creates owner membership via post-generation hook
- [ ] `tests/helpers.py` provides `as_project_member()` utility
- [ ] E2E seed script updated with non-staff test users and project memberships

---

## Decision Log

| # | Decision | Reason |
|---|----------|--------|
| 1 | `on_delete=SET_NULL` for all identity FKs | Deleting a User should not cascade-delete all their work |
| 2 | `on_delete=PROTECT` for Link.project FK | Consistent with Task→Project (PROTECT). Projects with links cannot be silently deleted |
| 3 | All identity FKs nullable | Empty string was the old sentinel; null is the FK equivalent |
| 4 | Agent.user stays nullable permanently | Agents may be pre-provisioned before authentication |
| 5 | Split triggered_by into trigger_source + actor | Field conflates identity and action; FK can't represent action labels |
| 6 | Denormalize project on Link | Polymorphic source resolution is too expensive for queryset scoping |
| 7 | Models implement `get_project_id()` (ProjectScopedModel) | Open/Closed: new models implement one method, no permission class changes. No type switching |
| 8 | Standalone scoping function, not mixin | Avoids MRO collision with ViewSets that already override `get_queryset()`. Explicit over implicit |
| 9 | `ProjectScopedPermission` calls `obj.get_project_id()`, never inspects model internals | Single Responsibility: models know their structure, permissions check access |
| 10 | Create-time auth in `perform_create()`, not in permission class | Context-dependent: project comes from body, URL, or parent entity. Generic class can't handle all cases without type switching |
| 11 | Auto-membership in view layer, not in `claim_task()` service | Dependency Inversion: domain service (tasks) should not depend on application module (prefs). View orchestrates |
| 12 | created_by server-set, never client-provided | Prevents identity spoofing; real audit trail |
| 13 | v1 serializers maintained with SlugRelatedField | Backward compat during v2 development period |
| 14 | Bootstrap migration for existing ProjectMembership data | Without it, authorization enforcement locks out all existing users on deployment |
| 15 | Step-by-step migration (7 steps) | Each step independently deployable and testable; rollback possible per step |
