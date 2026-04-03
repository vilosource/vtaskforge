from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.authorization import ProjectScopedPermission, require_project_membership, scope_queryset_to_user_projects
from rest_framework.permissions import IsAuthenticated
from core.pagination import VTFEventCursorPagination
from tasks.models import Task

from .models import TaskEvent
from .serializers import TaskEventSerializer


class TaskEventViewSet(mixins.ListModelMixin, GenericViewSet):
    """Read-only viewset for TaskEvents.

    Supports two access patterns:
    1. Nested under a task: GET /v1/tasks/{task_id}/events/
    2. Top-level with filters: GET /v1/events/?task=&event_type=&since=
    """

    serializer_class = TaskEventSerializer
    pagination_class = VTFEventCursorPagination
    permission_classes = [IsAuthenticated, ProjectScopedPermission]

    def get_queryset(self):
        # If nested under a task, filter by task_id from URL kwargs
        task_id = self.kwargs.get("task_id")
        if task_id is not None:
            return TaskEvent.objects.filter(task_id=task_id)

        # Top-level: apply optional query filters
        qs = TaskEvent.objects.all()
        qs = scope_queryset_to_user_projects(qs, self.request.user, TaskEvent)
        params = self.request.query_params

        task = params.get("task")
        if task:
            qs = qs.filter(task_id=task)

        event_type = params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        since = params.get("since")
        if since:
            qs = qs.filter(timestamp__gte=since)

        return qs

    def list(self, request, *args, **kwargs):
        # For nested endpoint, verify the task exists and check membership
        task_id = self.kwargs.get("task_id")
        if task_id is not None:
            try:
                task = Task.objects.get(pk=task_id)
            except Task.DoesNotExist:
                return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
            require_project_membership(request.user, task.project_id)
        return super().list(request, *args, **kwargs)
