from django.db.models import Count

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.authorization import (
    ProjectScopedPermission,
    RoleBasedPermission,
    require_project_membership,
    scope_queryset_to_user_projects,
)
from core.pagination import VTFCursorPagination
from tasks.models import Task
from core.versioning import VersionedSerializerMixin
from .models import Milestone, Workplan
from .serializers import MilestoneSerializer, WorkplanSerializer
from .serializers_v2 import MilestoneV2Serializer, WorkplanV2Serializer


class WorkplanViewSet(VersionedSerializerMixin, ModelViewSet):
    queryset = Workplan.objects.select_related("owner", "created_by").all()
    serializer_class = WorkplanSerializer
    serializer_class_v2 = WorkplanV2Serializer
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = scope_queryset_to_user_projects(queryset, self.request.user, Workplan)
        project_id = self.request.query_params.get('project')
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data.get("project")
        if project:
            pid = project.id if hasattr(project, "id") else project
            require_project_membership(self.request.user, pid)
        kwargs = {}
        if self.request.user.is_authenticated:
            kwargs["owner"] = self.request.user
            kwargs["created_by"] = self.request.user
        serializer.save(**kwargs)

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
        tasks = Task.objects.filter(workplan=workplan)
        total = tasks.count()
        status_counts = {
            row["status"]: row["count"]
            for row in tasks.values("status").annotate(count=Count("id"))
        }
        done_count = status_counts.get("done", 0)
        completed_percentage = round(done_count / total * 100, 1) if total > 0 else 0.0
        stats_data = {
            "workplan_id": workplan.id,
            "total_tasks": total,
            "by_status": status_counts,
            "completed_percentage": completed_percentage,
            "completed_tasks": done_count,
            "pending_tasks": status_counts.get("todo", 0),
            "in_progress_tasks": status_counts.get("doing", 0),
        }
        return Response(stats_data)


class WorkplanMilestonesView(APIView):
    """Nested endpoint: list and create milestones under a workplan."""

    def get_workplan(self, workplan_id):
        try:
            return Workplan.objects.get(pk=workplan_id)
        except Workplan.DoesNotExist:
            return None

    def get(self, request, workplan_id):
        workplan = self.get_workplan(workplan_id)
        if workplan is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        phases = Milestone.objects.filter(workplan=workplan)
        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(phases, request)
        if page is not None:
            serializer = MilestoneSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = MilestoneSerializer(phases, many=True)
        return Response(serializer.data)

    def post(self, request, workplan_id):
        workplan = self.get_workplan(workplan_id)
        if workplan is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data["workplan"] = workplan.id
        serializer = MilestoneSerializer(data=data)
        if serializer.is_valid():
            kwargs = {}
            if request.user.is_authenticated:
                kwargs["created_by"] = request.user
            serializer.save(**kwargs)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MilestoneViewSet(VersionedSerializerMixin, ModelViewSet):
    queryset = Milestone.objects.select_related("created_by").all()
    serializer_class = MilestoneSerializer
    serializer_class_v2 = MilestoneV2Serializer
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = scope_queryset_to_user_projects(queryset, self.request.user, Milestone)
        return queryset

    def perform_create(self, serializer):
        workplan = serializer.validated_data.get("workplan")
        if workplan:
            require_project_membership(self.request.user, workplan.project_id)
        kwargs = {}
        if self.request.user.is_authenticated:
            kwargs["created_by"] = self.request.user
        serializer.save(**kwargs)

    def update(self, request, *args, **kwargs):
        # Disable full PUT — PATCH only
        if not kwargs.get("partial", False):
            return Response(
                {"detail": "Method not allowed. Use PATCH for partial updates."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        milestone = self.get_object()
        if milestone.status != "pending":
            return Response(
                {"detail": "Only pending milestones can be activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # If all tasks are already terminal, skip to completed
        from tasks.state_machine import TERMINAL_STATUSES
        if milestone.tasks.exists() and not milestone.tasks.exclude(status__in=TERMINAL_STATUSES).exists():
            milestone.status = "completed"
        else:
            milestone.status = "active"
        milestone.save()
        serializer = self.get_serializer(milestone)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        milestone = self.get_object()
        if milestone.status != "active":
            return Response(
                {"detail": "Only active milestones can be completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        milestone.status = "completed"
        milestone.save()
        serializer = self.get_serializer(milestone)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        milestone = self.get_object()
        tasks = Task.objects.filter(milestone=milestone)
        total = tasks.count()
        status_counts = {
            row["status"]: row["count"]
            for row in tasks.values("status").annotate(count=Count("id"))
        }
        done_count = status_counts.get("done", 0)
        completed_percentage = round(done_count / total * 100, 1) if total > 0 else 0.0
        stats_data = {
            "milestone_id": milestone.id,
            "total_tasks": total,
            "by_status": status_counts,
            "completed_percentage": completed_percentage,
            "completed_tasks": done_count,
            "pending_tasks": status_counts.get("todo", 0),
            "in_progress_tasks": status_counts.get("doing", 0),
        }
        return Response(stats_data)
