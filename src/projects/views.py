from django.db.models import Count

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.pagination import VTFCursorPagination
from workplans.models import Workplan
from workplans.serializers import WorkplanSerializer
from .models import Project
from .serializers import ProjectSerializer


class ProjectViewSet(ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
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
        project = self.get_object()
        if project.status == "archived":
            return Response(
                {"detail": "Project is already archived."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project.status = "archived"
        project.save()
        serializer = self.get_serializer(project)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        project = self.get_object()

        from tasks.models import Task

        # Get all tasks from workplans belonging to this project
        tasks = Task.objects.filter(workplan__project=project)

        total = tasks.count()
        status_counts = {
            row["status"]: row["count"]
            for row in tasks.values("status").annotate(count=Count("id"))
        }
        done_count = status_counts.get("done", 0)
        completed_percentage = round(done_count / total * 100, 1) if total > 0 else 0.0

        # Count workplans by status using the now-existing Workplan.project FK
        workplan_queryset = Workplan.objects.filter(project=project)
        workplan_counts = {
            row["status"]: row["count"]
            for row in workplan_queryset.values("status").annotate(count=Count("id"))
        }

        stats_data = {
            "project_id": project.id,
            "total_tasks": total,
            "backlog_tasks": 0,  # Will be > 0 after task 9.3 adds Task.project FK
            "workplan_tasks": total,  # For now, all tasks are workplan tasks
            "by_status": status_counts,
            "completed_percentage": completed_percentage,
            "workplans": workplan_counts,
        }
        return Response(stats_data)


class ProjectWorkplansView(APIView):
    """Nested endpoint: list workplans under a project."""

    def get_project(self, project_id):
        try:
            return Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return None

    def get(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Filter workplans by the project from the URL
        workplans = Workplan.objects.filter(project=project)

        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(workplans, request)
        if page is not None:
            serializer = WorkplanSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = WorkplanSerializer(workplans, many=True)
        return Response(serializer.data)


class ProjectBacklogView(APIView):
    """Nested endpoint: list tasks without workplan (backlog) under a project."""

    def get_project(self, project_id):
        try:
            return Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return None

    def get(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # For now, since Task.project FK doesn't exist yet (comes in task 9.3),
        # we'll return empty results. This endpoint will work once that FK is added
        # and we can filter Task.objects.filter(project=project, workplan__isnull=True).
        from tasks.models import Task
        from tasks.serializers import TaskSerializer

        backlog_tasks = Task.objects.none()

        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(backlog_tasks, request)
        if page is not None:
            serializer = TaskSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = TaskSerializer(backlog_tasks, many=True)
        return Response(serializer.data)