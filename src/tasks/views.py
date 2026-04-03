from datetime import timedelta

from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from agents.models import Agent
from prefs.mixins import TrackAccessMixin
from core.pagination import VTFCursorPagination, VTFNoteCursorPagination
from projects.models import Project
from workplans.models import Milestone

from events.services import record_event
from .exceptions import InvalidTransition
from .models import Note, Task
from .review_policy import get_effective_review_flags
from .serializers import NoteSerializer, TaskDetailSerializer, TaskSerializer
from .services import claim_task, ClaimError, find_claimable_tasks, resolve_dependencies
from .state_machine import get_valid_transitions, perform_transition, NON_TERMINAL_STATUSES, TERMINAL_STATUSES

DEFAULT_CLAIM_TIMEOUT_MINUTES = 30


def invalid_transition_response(exc):
    """Return a 422/409 response for transition errors.

    GuardViolation (business rule blocked): 409 GUARD_VIOLATION
    InvalidTransition (wrong status): 422 INVALID_TRANSITION
    """
    from tasks.exceptions import GuardViolation
    if isinstance(exc, GuardViolation):
        return Response(
            {
                "error": {
                    "code": "GUARD_VIOLATION",
                    "message": str(exc),
                    "details": {
                        "current_status": exc.current_status,
                        "requested_status": exc.requested_status,
                        "guard": exc.guard_name,
                    },
                }
            },
            status=status.HTTP_409_CONFLICT,
        )
    return Response(
        {
            "error": {
                "code": "INVALID_TRANSITION",
                "message": f"Cannot transition from '{exc.current_status}' to '{exc.requested_status}'",
                "details": {
                    "current_status": exc.current_status,
                    "requested_status": exc.requested_status,
                    "valid_transitions": exc.valid_transitions,
                },
            }
        },
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


class TaskViewSet(TrackAccessMixin, ModelViewSet):
    access_resource_type = "task"
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        """Use TaskDetailSerializer on retrieve when ?expand= is present."""
        if self.action == "retrieve" and self.request.query_params.get("expand"):
            return TaskDetailSerializer
        return TaskSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        expand_param = self.request.query_params.get("expand", "")
        expand = [f.strip() for f in expand_param.split(",") if f.strip()]
        context["expand"] = expand
        return context

    def get_queryset(self):
        qs = Task.objects.select_related("project", "milestone", "workplan").all()
        params = self.request.query_params

        task_status = params.get("status")
        if task_status:
            statuses = [s.strip() for s in task_status.split(",") if s.strip()]
            qs = qs.filter(status__in=statuses)

        project = params.get("project")
        if project:
            qs = qs.filter(project_id=project)

        milestone = params.get("milestone")
        if milestone:
            qs = qs.filter(milestone_id=milestone)

        workplan = params.get("workplan")
        workplan_isnull = params.get("workplan__isnull")
        if workplan:
            qs = qs.filter(workplan_id=workplan)
        elif workplan_isnull and workplan_isnull.lower() == "true":
            qs = qs.filter(workplan__isnull=True)

        assigned_to = params.get("assigned_to")
        if assigned_to:
            qs = qs.filter(assigned_to=assigned_to)

        labels = params.get("labels")
        if labels:
            label_list = [l.strip() for l in labels.split(",") if l.strip()]
            # Filter tasks that have any of the specified labels
            from django.db.models import Q
            label_queries = Q()
            for label in label_list:
                label_queries |= Q(labels__contains=[label])
            if label_queries:
                qs = qs.filter(label_queries)

        return qs

    def update(self, request, *args, **kwargs):
        # Disable full PUT — PATCH only
        if not kwargs.get("partial", False):
            return Response(
                {"detail": "Method not allowed. Use PATCH for partial updates."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().update(request, *args, **kwargs)

    # -------------------------------------------------------------------------
    # Lifecycle actions
    # -------------------------------------------------------------------------

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """draft -> pending_start_review (if needs_review_before_start) or todo."""
        task = self.get_object()
        before_start, _ = get_effective_review_flags(task)
        target = "pending_start_review" if before_start else "todo"
        try:
            perform_transition(task, target, trigger_source="submit")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        """todo -> doing. Atomic claim with tag matching, assignment, and dependency checks."""
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "agent_id required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Look up agent from DB to get registered tags; body tags override DB tags
        try:
            agent = Agent.objects.get(pk=agent_id)
        except Agent.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Agent not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        agent_tags = request.data.get("tags") if request.data.get("tags") is not None else agent.tags

        try:
            task = claim_task(pk, agent_id, agent_tags)
        except Task.DoesNotExist:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Task not found"}},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ClaimError as exc:
            # Map service-level codes to HTTP response error codes
            code_map = {
                "ALREADY_CLAIMED": "ALREADY_CLAIMED",
                "FORBIDDEN": "FORBIDDEN",
                "tag_mismatch": "VALIDATION_ERROR",
                "deps_unmet": "DEPENDENCY_UNMET",
            }
            http_code = code_map.get(exc.code, exc.code)
            body = {"error": {"code": http_code, "message": exc.message}}
            if exc.details:
                body["error"]["details"] = exc.details
            return Response(body, status=exc.status_code)

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def claimable(self, request):
        """GET /v1/tasks/claimable?tags=executor,opus&project=:id — tasks claimable by agent with given tags."""
        tags_param = request.query_params.get("tags", "")
        tags = [t for t in tags_param.split(",") if t] if tags_param else []
        agent_id = request.query_params.get("agent_id", "")
        project = request.query_params.get("project", "")

        # If agent_id given and no tags param, look up agent tags from DB
        if agent_id and not tags:
            try:
                agent = Agent.objects.get(pk=agent_id)
                tags = agent.tags or []
            except Agent.DoesNotExist:
                tags = []

        tasks = find_claimable_tasks(
            project_id=project or None,
            tags=tags or None,
            agent_id=agent_id or None,
        )

        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(tasks, request)
        if page is not None:
            serializer = TaskSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def unclaim(self, request, pk=None):
        """doing -> todo. Clears claim fields.

        Uses the state machine for the status transition, then creates a
        separate 'unclaimed' event. Produces both status_changed and unclaimed events.
        Only valid when the task is in 'doing' status.
        """
        task = self.get_object()
        previous_agent = task.claimed_by
        if task.status != "doing":
            exc = InvalidTransition(task.status, "todo", get_valid_transitions(task.status))
            return invalid_transition_response(exc)
        try:
            perform_transition(task, "todo", trigger_source="unclaim")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)

        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        record_event(
            task,
            "unclaimed",
            data={"agent_id": previous_agent} if previous_agent else {},
            trigger_source="unclaim",
        )

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """doing -> pending_completion_review (if needs_review_on_completion) or done."""
        task = self.get_object()
        _, on_completion = get_effective_review_flags(task)
        target = "pending_completion_review" if on_completion else "done"
        try:
            perform_transition(task, target, trigger_source="complete")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        """doing -> needs_attention."""
        task = self.get_object()
        try:
            perform_transition(task, "needs_attention", trigger_source="fail")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        # Clear stale claim fields (matching unclaim and expire_stale_claims behavior)
        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at"])
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def recover(self, request, pk=None):
        """needs_attention -> todo (re-queue) or draft (major rework)."""
        task = self.get_object()
        target = request.data.get("target")
        reason = request.data.get("reason", "").strip()

        if target not in ("todo", "draft"):
            return Response(
                {"error": {"code": "INVALID_TARGET", "message": "target must be 'todo' or 'draft'"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not reason:
            return Response(
                {"error": {"code": "REASON_REQUIRED", "message": "reason is required for recovery"}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if task.status != "needs_attention":
            return Response(
                {"error": {"code": "NOT_NEEDS_ATTENTION", "message": f"Task is '{task.status}', not 'needs_attention'"}},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            perform_transition(task, target, trigger_source="recover")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)

        # Clear stale claim fields
        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        # Increment retry_count only for re-queue (todo), not major rework (draft)
        if target == "todo":
            task.retry_count += 1
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "retry_count"])

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def resubmit(self, request, pk=None):
        """changes_requested -> review_return_to value. Return 400 if review_return_to not set."""
        task = self.get_object()
        if not task.review_return_to:
            return Response(
                {"detail": "review_return_to is not set on this task."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            perform_transition(task, task.review_return_to, trigger_source="resubmit")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        """todo/doing -> blocked."""
        task = self.get_object()
        try:
            perform_transition(task, "blocked", trigger_source="block")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        """blocked -> todo (default)."""
        task = self.get_object()
        try:
            perform_transition(task, "todo", trigger_source="unblock")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def defer(self, request, pk=None):
        """any non-terminal -> deferred."""
        task = self.get_object()
        try:
            perform_transition(task, "deferred", trigger_source="defer")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """any non-terminal -> cancelled."""
        task = self.get_object()
        try:
            perform_transition(task, "cancelled", trigger_source="cancel")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def heartbeat(self, request, pk=None):
        """Extends claim_expires_at on a doing task. Return 400 if not doing."""
        task = self.get_object()
        if task.status != "doing":
            return Response(
                {"detail": "Heartbeat is only valid for tasks in 'doing' status."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        timeout = task.claim_timeout or timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
        task.claim_expires_at = timezone.now() + timeout
        task.save(update_fields=["claim_expires_at", "updated_at"])
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def progress(self, request, pk=None):
        """Placeholder — accepts message, returns 200 (events system in 1.10)."""
        task = self.get_object()
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Set assigned_to field."""
        task = self.get_object()
        assigned_to = request.data.get("assigned_to")
        if not assigned_to:
            return Response(
                {"detail": "assigned_to is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        task.assigned_to = assigned_to
        task.save(update_fields=["assigned_to", "updated_at"])
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def unassign(self, request, pk=None):
        """Clear assigned_to field."""
        task = self.get_object()
        task.assigned_to = None
        task.save(update_fields=["assigned_to", "updated_at"])
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def reset(self, request, pk=None):
        """Admin force-transition: bypass state machine, move task to any valid status."""
        task = self.get_object()
        target_status = request.data.get("status")
        reason = request.data.get("reason", "").strip()

        all_statuses = NON_TERMINAL_STATUSES | TERMINAL_STATUSES
        if not target_status or target_status not in all_statuses:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": f"Invalid status '{target_status}'. Must be one of: {sorted(all_statuses)}",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not reason:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "reason is required for force transitions",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        old_status = task.status
        task.status = target_status
        # Clear claim fields when resetting to a non-doing status
        update_fields = ["status", "updated_at"]
        if target_status != "doing":
            task.claimed_by = None
            task.claimed_at = None
            task.claim_expires_at = None
            update_fields += ["claimed_by", "claimed_at", "claim_expires_at"]
        task.save(update_fields=update_fields)

        record_event(
            task,
            "force_transition",
            data={"from": old_status, "to": target_status, "reason": reason},
            trigger_source="admin",
        )

        serializer = self.get_serializer(task)
        return Response(serializer.data)


class NoteViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = NoteSerializer
    pagination_class = VTFNoteCursorPagination

    def get_task(self):
        task_id = self.kwargs["task_id"]
        try:
            return Task.objects.get(pk=task_id)
        except Task.DoesNotExist:
            return None

    def get_queryset(self):
        task_id = self.kwargs["task_id"]
        return Note.objects.filter(task_id=task_id)

    def list(self, request, *args, **kwargs):
        if self.get_task() is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        task = self.get_task()
        serializer.save(task=task)

    def create(self, request, *args, **kwargs):
        if self.get_task() is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().create(request, *args, **kwargs)


class MilestoneTasksView(APIView):
    """Nested endpoint: list and create tasks under a milestone.
    Auto-sets milestone, workplan, and project from milestone.workplan.project on create.
    """

    def get_milestone(self, milestone_id):
        try:
            return Milestone.objects.select_related("workplan__project").get(pk=milestone_id)
        except Milestone.DoesNotExist:
            return None

    def get(self, request, milestone_id):
        milestone = self.get_milestone(milestone_id)
        if milestone is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        tasks = Task.objects.filter(milestone=milestone)
        # Apply same query filters as the viewset
        task_status = request.query_params.get("status")
        if task_status:
            tasks = tasks.filter(status=task_status)
        assigned_to = request.query_params.get("assigned_to")
        if assigned_to:
            tasks = tasks.filter(assigned_to=assigned_to)
        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(tasks, request)
        if page is not None:
            serializer = TaskSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request, milestone_id):
        milestone = self.get_milestone(milestone_id)
        if milestone is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data["milestone"] = milestone.id
        data["workplan"] = milestone.workplan_id
        data["project"] = milestone.workplan.project_id
        serializer = TaskSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProjectTasksView(APIView):
    """Nested endpoint: list and create backlog tasks under a project.
    Auto-sets project from URL, leaves workplan and milestone null for backlog tasks.
    """

    def get_project(self, project_id):
        try:
            return Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return None

    def get(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        # List backlog tasks (tasks with no workplan)
        tasks = Task.objects.filter(project=project, workplan__isnull=True)
        # Apply same query filters as the viewset
        task_status = request.query_params.get("status")
        if task_status:
            tasks = tasks.filter(status=task_status)
        assigned_to = request.query_params.get("assigned_to")
        if assigned_to:
            tasks = tasks.filter(assigned_to=assigned_to)
        labels = request.query_params.get("labels")
        if labels:
            label_list = [l.strip() for l in labels.split(",") if l.strip()]
            from django.db.models import Q
            label_queries = Q()
            for label in label_list:
                label_queries |= Q(labels__contains=[label])
            if label_queries:
                tasks = tasks.filter(label_queries)
        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(tasks, request)
        if page is not None:
            serializer = TaskSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data["project"] = project.id
        # Explicitly set workplan and milestone to None for backlog tasks
        data["workplan"] = None
        data["milestone"] = None
        serializer = TaskSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
