from django.db.models import Q
from django.http import Http404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.authorization import (
    ProjectScopedPermission,
    RoleBasedPermission,
    scope_queryset_to_user_projects,
)
from prefs.mixins import TrackAccessMixin
from projects.models import Project

from .admission import near_matches
from .models import ProjectVariable
from .serializers import ProjectVariableSerializer


class ProjectVariableViewSet(TrackAccessMixin, ModelViewSet):
    """CRUD for a project's secret-variable declarations.

    Nested under /projects/<project_id>/variables/. The parent project is
    resolved by PK or slug and scoped to the requesting user's projects (404 if
    not accessible). Detail routes address variables by their surrogate PK.
    """

    access_resource_type = "project_variable"
    serializer_class = ProjectVariableSerializer
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def _get_project(self):
        ident = self.kwargs["project_id"]
        qs = scope_queryset_to_user_projects(Project.objects.all(), self.request.user, Project)
        project = qs.filter(Q(pk=ident) | Q(slug=ident)).first()
        if project is None:
            raise Http404
        return project

    def get_queryset(self):
        project = self._get_project()
        qs = ProjectVariable.objects.filter(project=project)
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        return qs

    def create(self, request, *args, **kwargs):
        project = self._get_project()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        role = serializer.validated_data["role"]

        # Exact duplicate — (project, name, role) is unique. Checked explicitly
        # because `project` is URL-bound, not a serializer field, so DRF can't
        # attach a UniqueTogetherValidator.
        if ProjectVariable.objects.filter(project=project, name=name, role=role).exists():
            return Response(
                {"name": [f"A {role} variable named '{name}' already exists for this project."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        force = request.query_params.get("force", "").lower() == "true"
        if not force:
            existing = list(
                ProjectVariable.objects.filter(project=project, role=role)
                .values_list("name", flat=True)
            )
            matches = near_matches(name, existing)
            if matches:
                return Response(
                    {"name": [
                        f"'{name}' is similar to existing {role} variable(s): "
                        f"{', '.join(matches)}. Pass ?force=true to create anyway."
                    ]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer.save(project=project)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        for field in ("name", "role"):
            if field in request.data and request.data[field] != getattr(instance, field):
                return Response(
                    {field: [f"'{field}' is immutable; delete and recreate the variable instead."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().partial_update(request, *args, **kwargs)
