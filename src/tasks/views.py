from datetime import timedelta

from django.utils import timezone
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from workplans.models import Phase

from .exceptions import InvalidTransition
from .models import Note, Task
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
        qs = Task.objects.all()
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
        """draft -> todo (review flag logic added in 1.11, always go to todo for now)."""
        task = self.get_object()
        try:
            perform_transition(task, "todo", triggered_by="submit")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def claim(self, request, pk=None):
        """todo -> doing. Requires agent_id in body. Sets claim fields."""
        task = self.get_object()
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response(
                {"detail": "agent_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            perform_transition(task, "doing", triggered_by=agent_id)
        except InvalidTransition as exc:
            return invalid_transition_response(exc)

        now = timezone.now()
        timeout = timedelta(minutes=DEFAULT_CLAIM_TIMEOUT_MINUTES)
        task.claimed_by = agent_id
        task.claimed_at = now
        task.claim_expires_at = now + timeout
        task.save(update_fields=["claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        serializer = self.get_serializer(task)
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

        task.status = "todo"
        task.claimed_by = None
        task.claimed_at = None
        task.claim_expires_at = None
        task.save(update_fields=["status", "claimed_by", "claimed_at", "claim_expires_at", "updated_at"])

        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """doing -> done (review flag logic added in 1.11, always go to done for now)."""
        task = self.get_object()
        try:
            perform_transition(task, "done", triggered_by="complete")
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
