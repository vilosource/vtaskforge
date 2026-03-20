from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from workplans.models import Phase

from .exceptions import InvalidTransition
from .models import Note, Task
from .review_policy import get_effective_review_flags
from .serializers import NoteSerializer, TaskSerializer
from .state_machine import perform_transition

DEFAULT_CLAIM_TIMEOUT_MINUTES = 30


def invalid_transition_response(exc):
    """Return a 422 response with the standard INVALID_TRANSITION error format."""
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


class TaskViewSet(ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Task.objects.select_related("phase", "workplan").all()
        params = self.request.query_params

        task_status = params.get("status")
        if task_status:
            qs = qs.filter(status=task_status)

        phase = params.get("phase")
        if phase:
            qs = qs.filter(phase_id=phase)

        workplan = params.get("workplan")
        if workplan:
            qs = qs.filter(workplan_id=workplan)

        assigned_to = params.get("assigned_to")
        if assigned_to:
            qs = qs.filter(assigned_to=assigned_to)

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
            perform_transition(task, target, triggered_by="submit")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        """todo -> doing. Atomic claim with tag matching, assignment, and dependency checks."""
        agent_id = request.data.get("agent_id")
        agent_tags = request.data.get("tags", [])
        if not agent_id:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "agent_id required"}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(pk=pk)
            except Task.DoesNotExist:
                return Response(
                    {"error": {"code": "NOT_FOUND", "message": "Task not found"}},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Status check
            if task.status != "todo":
                return Response(
                    {
                        "error": {
                            "code": "ALREADY_CLAIMED",
                            "message": "Task is not claimable",
                            "details": {"current_status": task.status},
                        }
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # Assignment check
            if task.assigned_to and task.assigned_to != agent_id:
                return Response(
                    {"error": {"code": "FORBIDDEN", "message": "Task assigned to another agent"}},
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Tag matching — task.requires must be subset of agent_tags
            if task.requires:
                if not set(task.requires).issubset(set(agent_tags)):
                    return Response(
                        {
                            "error": {
                                "code": "VALIDATION_ERROR",
                                "message": "Agent tags do not match task requirements",
                                "details": {
                                    "requires": task.requires,
                                    "agent_tags": agent_tags,
                                },
                            }
                        },
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )

            # Dependency check — all depends_on links must have target tasks in "done" status
            from links.models import Link
            depends_on_links = Link.objects.filter(
                source_type="task", source_id=task.id, link_type="depends_on"
            )
            for link in depends_on_links:
                try:
                    dep_task = Task.objects.get(pk=link.target_id)
                    if dep_task.status != "done":
                        return Response(
                            {
                                "error": {
                                    "code": "DEPENDENCY_UNMET",
                                    "message": f"Dependency {link.target_id} not done",
                                    "details": {
                                        "dependency_id": link.target_id,
                                        "dependency_status": dep_task.status,
                                    },
                                }
                            },
                            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        )
                except Task.DoesNotExist:
                    pass  # External dependency — skip

            # All checks passed — perform claim
            perform_transition(task, "doing", triggered_by=agent_id)
            task.claimed_by = agent_id
            task.claimed_at = timezone.now()
            timeout = task.claim_timeout or timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
            task.claim_expires_at = timezone.now() + timeout
            task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

            try:
                from events.models import TaskEvent
                TaskEvent.objects.create(
                    task=task,
                    event_type="claimed",
                    data={"agent_id": agent_id},
                    triggered_by=agent_id,
                )
            except Exception:
                pass

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def claimable(self, request):
        """GET /v1/tasks/claimable?tags=executor,opus — tasks claimable by agent with given tags."""
        tags_param = request.query_params.get("tags", "")
        tags = [t for t in tags_param.split(",") if t] if tags_param else []
        agent_id = request.query_params.get("agent_id", "")

        tasks = Task.objects.filter(status="todo")

        # Exclude tasks with unmet dependencies
        from links.models import Link
        task_ids_with_deps = Link.objects.filter(
            source_type="task", link_type="depends_on"
        ).values_list("source_id", flat=True)
        unmet_task_ids = []
        for tid in set(task_ids_with_deps):
            deps = Link.objects.filter(source_type="task", source_id=tid, link_type="depends_on")
            for dep in deps:
                try:
                    dep_task = Task.objects.get(pk=dep.target_id)
                    if dep_task.status != "done":
                        unmet_task_ids.append(tid)
                        break
                except Task.DoesNotExist:
                    pass
        tasks = tasks.exclude(id__in=unmet_task_ids)

        # Filter by tags if provided — task.requires must be subset of provided tags
        if tags:
            filtered_ids = [t.id for t in tasks if not t.requires or set(t.requires).issubset(set(tags))]
            tasks = tasks.filter(id__in=filtered_ids)

        # Filter by assignment — exclude tasks assigned to other agents
        if agent_id:
            unassigned = tasks.filter(assigned_to__isnull=True) | tasks.filter(assigned_to="")
            assigned_to_me = tasks.filter(assigned_to=agent_id)
            tasks = Task.objects.filter(id__in=list(unassigned.values_list("id", flat=True)) + list(assigned_to_me.values_list("id", flat=True)))

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def unclaim(self, request, pk=None):
        """doing -> todo. Clears claim fields.

        This is an administrative release action that directly sets status to todo
        and clears claim fields. Only valid when the task is in 'doing' status.
        """
        task = self.get_object()
        if task.status != "doing":
            exc = InvalidTransition(task.status, "todo", [])
            return invalid_transition_response(exc)

        previous_agent = task.claimed_by
        task.status = "todo"
        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        task.save(update_fields=["status", "claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        try:
            from events.models import TaskEvent
            TaskEvent.objects.create(
                task=task,
                event_type="unclaimed",
                data={"agent_id": previous_agent} if previous_agent else {},
                triggered_by=previous_agent or "",
            )
        except Exception:
            pass

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """doing -> pending_completion_review (if needs_review_on_completion) or done."""
        task = self.get_object()
        _, on_completion = get_effective_review_flags(task)
        target = "pending_completion_review" if on_completion else "done"
        try:
            perform_transition(task, target, triggered_by="complete")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        """doing -> needs_attention."""
        task = self.get_object()
        try:
            perform_transition(task, "needs_attention", triggered_by="fail")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
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
            perform_transition(task, task.review_return_to, triggered_by="resubmit")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        """todo/doing -> blocked."""
        task = self.get_object()
        try:
            perform_transition(task, "blocked", triggered_by="block")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def unblock(self, request, pk=None):
        """blocked -> todo (default)."""
        task = self.get_object()
        try:
            perform_transition(task, "todo", triggered_by="unblock")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def defer(self, request, pk=None):
        """any non-terminal -> deferred."""
        task = self.get_object()
        try:
            perform_transition(task, "deferred", triggered_by="defer")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """any non-terminal -> cancelled."""
        task = self.get_object()
        try:
            perform_transition(task, "cancelled", triggered_by="cancel")
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


class NoteViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = NoteSerializer

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


class PhaseTasksView(APIView):
    """Nested endpoint: list and create tasks under a phase.
    Auto-sets phase and workplan from phase.workplan on create.
    """

    def get_phase(self, phase_id):
        try:
            return Phase.objects.get(pk=phase_id)
        except Phase.DoesNotExist:
            return None

    def get(self, request, phase_id):
        phase = self.get_phase(phase_id)
        if phase is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        tasks = Task.objects.filter(phase=phase)
        # Apply same query filters as the viewset
        task_status = request.query_params.get("status")
        if task_status:
            tasks = tasks.filter(status=task_status)
        assigned_to = request.query_params.get("assigned_to")
        if assigned_to:
            tasks = tasks.filter(assigned_to=assigned_to)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    def post(self, request, phase_id):
        phase = self.get_phase(phase_id)
        if phase is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data["phase"] = phase.id
        data["workplan"] = phase.workplan_id
        serializer = TaskSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
