from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Workplan
from .serializers import WorkplanSerializer


class WorkplanViewSet(ModelViewSet):
    queryset = Workplan.objects.all()
    serializer_class = WorkplanSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def update(self, request, *args, **kwargs):
        # Disable full PUT — PATCH only
        if not kwargs.get("partial", False):
            return Response(
                {"detail": "Method not allowed. Use PATCH for partial updates."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        workplan = self.get_object()
        if workplan.status == "archived":
            return Response(
                {"detail": "Workplan is already archived."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workplan.status = "archived"
        workplan.save()
        serializer = self.get_serializer(workplan)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        workplan = self.get_object()
        if workplan.status == "completed":
            return Response(
                {"detail": "Workplan is already completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if workplan.status == "archived":
            return Response(
                {"detail": "Cannot complete an archived workplan."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        workplan.status = "completed"
        workplan.save()
        serializer = self.get_serializer(workplan)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        workplan = self.get_object()
        # Placeholder stats — task counts will be populated in later tasks
        stats_data = {
            "workplan_id": workplan.id,
            "total_tasks": 0,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "in_progress_tasks": 0,
        }
        return Response(stats_data)
