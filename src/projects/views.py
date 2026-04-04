from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, ProtectedError

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.authorization import (
    ProjectScopedPermission,
    RoleBasedPermission,
    scope_queryset_to_user_projects,
)
from core.pagination import VTFCursorPagination
from workplans.models import Workplan
from workplans.serializers import WorkplanSerializer
from prefs.mixins import TrackAccessMixin
from prefs.models import ProjectMembership
from prefs.permissions import HasProjectMembership
from prefs.views import ProjectMembershipSerializer
from core.versioning import VersionedSerializerMixin
from .models import Project
from .serializers import ProjectSerializer
from .serializers_v2 import ProjectV2Serializer


class ProjectViewSet(VersionedSerializerMixin, TrackAccessMixin, ModelViewSet):
    access_resource_type = "project"
    queryset = Project.objects.select_related("owner", "created_by").all()
    serializer_class = ProjectSerializer
    serializer_class_v2 = ProjectV2Serializer
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = super().get_queryset()
        qs = scope_queryset_to_user_projects(qs, self.request.user, Project)
        return qs

    def perform_create(self, serializer):
        kwargs = {}
        if self.request.user.is_authenticated:
            kwargs["owner"] = self.request.user
            kwargs["created_by"] = self.request.user
        project = serializer.save(**kwargs)
        if self.request.user.is_authenticated:
            ProjectMembership.objects.get_or_create(
                user=self.request.user,
                project_id=project.id,
                defaults={"role": "owner"},
            )

    def update(self, request, *args, **kwargs):
        # Disable full PUT — PATCH only
        if not kwargs.get("partial", False):
            return Response(
                {"detail": "Method not allowed. Use PATCH for partial updates."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {
                    "error": {
                        "code": "PROTECTED",
                        "message": "Cannot delete project: it still has tasks. Delete or reassign tasks first.",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

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

        # Get all tasks in this project (both workplan and backlog)
        all_tasks = Task.objects.filter(project=project)
        backlog_tasks = all_tasks.filter(workplan__isnull=True)
        workplan_tasks = all_tasks.filter(workplan__isnull=False)

        total = all_tasks.count()
        status_counts = {
            row["status"]: row["count"]
            for row in all_tasks.values("status").annotate(count=Count("id"))
        }
        done_count = status_counts.get("done", 0)
        completed_percentage = round(done_count / total * 100, 1) if total > 0 else 0.0

        # Count workplans by status
        workplan_queryset = Workplan.objects.filter(project=project)
        workplan_counts = {
            row["status"]: row["count"]
            for row in workplan_queryset.values("status").annotate(count=Count("id"))
        }

        stats_data = {
            "project_id": project.id,
            "total_tasks": total,
            "backlog_tasks": backlog_tasks.count(),
            "workplan_tasks": workplan_tasks.count(),
            "by_status": status_counts,
            "completed_percentage": completed_percentage,
            "workplans": workplan_counts,
        }
        return Response(stats_data)


class ProjectWorkplansView(APIView):
    """Nested endpoint: list workplans under a project."""

    permission_classes = [HasProjectMembership]

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

    permission_classes = [HasProjectMembership]

    def get_project(self, project_id):
        try:
            return Project.objects.get(pk=project_id)
        except Project.DoesNotExist:
            return None

    def get(self, request, project_id):
        project = self.get_project(project_id)
        if project is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from tasks.models import Task
        from tasks.serializers import TaskSerializer
        from tasks.serializers_v2 import TaskV2Serializer

        SerializerClass = TaskV2Serializer if getattr(request, "version", "v1") == "v2" else TaskSerializer
        backlog_tasks = Task.objects.filter(project=project, workplan__isnull=True)

        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(backlog_tasks, request)
        ctx = {"request": request}
        if page is not None:
            serializer = SerializerClass(page, many=True, context=ctx)
            return paginator.get_paginated_response(serializer.data)
        serializer = SerializerClass(backlog_tasks, many=True, context=ctx)
        return Response(serializer.data)


class ProjectMemberView(APIView):
    """GET/POST /v1/projects/<project_id>/members/ — list and add members."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated(), HasProjectMembership()]

    def get(self, request, project_id):
        members = ProjectMembership.objects.select_related("user").filter(
            project_id=project_id
        )
        if getattr(request, "version", "v1") == "v2":
            from prefs.serializers_v2 import ProjectMembershipV2Serializer
            serializer = ProjectMembershipV2Serializer(members, many=True)
        else:
            serializer = ProjectMembershipSerializer(members, many=True)
        return Response({"results": serializer.data})

    def post(self, request, project_id):
        username = request.data.get("username")
        role = request.data.get("role", "member")

        if not username:
            return Response(
                {"detail": "username is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {"detail": f"User '{username}' not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = ProjectMembership.objects.create(
                user=user, project_id=project_id, role=role
            )
        except IntegrityError:
            return Response(
                {"detail": f"User '{username}' is already a member of this project."},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = ProjectMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectMemberDetailView(APIView):
    """PATCH/DELETE /v1/projects/<project_id>/members/<pk>/ — update role or remove."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, project_id, pk):
        role = request.data.get("role")
        if not role:
            return Response(
                {"detail": "role is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            membership = ProjectMembership.objects.get(pk=pk, project_id=project_id)
        except ProjectMembership.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        membership.role = role
        membership.save(update_fields=["role"])
        serializer = ProjectMembershipSerializer(membership)
        return Response(serializer.data)

    def delete(self, request, project_id, pk):
        try:
            membership = ProjectMembership.objects.get(pk=pk, project_id=project_id)
        except ProjectMembership.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        membership.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)