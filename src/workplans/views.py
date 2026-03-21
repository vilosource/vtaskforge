from django.db.models import Count

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.pagination import VTFCursorPagination
from tasks.models import Task
from .models import Milestone, Workplan
from .serializers import MilestoneSerializer, WorkplanSerializer


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
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MilestoneViewSet(ModelViewSet):
    queryset = Milestone.objects.all()
    serializer_class = MilestoneSerializer
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
    def activate(self, request, pk=None):
        milestone = self.get_object()
        if milestone.status != "pending":
            return Response(
                {"detail": "Only pending milestones can be activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
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
