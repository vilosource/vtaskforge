from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.authorization import (
    ProjectScopedPermission,
    RoleBasedPermission,
    require_project_membership,
    scope_queryset_to_user_projects,
)
from core.versioning import VersionedSerializerMixin
from .models import Link
from .serializers import LinkSerializer
from .serializers_v2 import LinkV2Serializer, LinkV2WriteSerializer, build_link_entity_cache


class LinkViewSet(VersionedSerializerMixin, ModelViewSet):
    queryset = Link.objects.select_related("project", "created_by").all()
    serializer_class = LinkSerializer
    serializer_class_v2 = LinkV2Serializer
    serializer_classes_v2 = {"create": LinkV2WriteSerializer}
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def list(self, request, *args, **kwargs):
        """Override list to add entity cache for v2 batch prefetch."""
        if getattr(request, "version", "v1") == "v2":
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            links = page if page is not None else list(queryset)
            cache = build_link_entity_cache(links)
            serializer = self.get_serializer(links, many=True, context={**self.get_serializer_context(), "entity_cache": cache})
            if page is not None:
                return self.get_paginated_response(serializer.data)
            return Response(serializer.data)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        kwargs = {}
        if self.request.user.is_authenticated:
            kwargs["created_by"] = self.request.user

        # Resolve project from source entity
        source_type = serializer.validated_data.get("source_type")
        source_id = serializer.validated_data.get("source_id")
        project = self._resolve_project(source_type, source_id)
        if project:
            require_project_membership(self.request.user, project.id)
            kwargs["project"] = project

        serializer.save(**kwargs)

    def _resolve_project(self, source_type, source_id):
        """Resolve the project FK from the link's source entity."""
        if not source_type or not source_id:
            return None
        try:
            if source_type == "task":
                from tasks.models import Task
                return Task.objects.select_related("project").get(pk=source_id).project
            elif source_type == "workplan":
                from workplans.models import Workplan
                return Workplan.objects.select_related("project").get(pk=source_id).project
            elif source_type == "milestone":
                from workplans.models import Milestone
                return Milestone.objects.select_related("workplan__project").get(pk=source_id).workplan.project
        except Exception:
            return None
        return None

    def get_queryset(self):
        queryset = Link.objects.select_related("project", "created_by").all()
        queryset = scope_queryset_to_user_projects(queryset, self.request.user, Link)
        source_id = self.request.query_params.get("source_id")
        target_id = self.request.query_params.get("target_id")
        source_type = self.request.query_params.get("source_type")
        link_type = self.request.query_params.get("link_type")

        if source_id is not None:
            queryset = queryset.filter(source_id=source_id)
        if target_id is not None:
            queryset = queryset.filter(target_id=target_id)
        if source_type is not None:
            queryset = queryset.filter(source_type=source_type)
        if link_type is not None:
            queryset = queryset.filter(link_type=link_type)

        return queryset

    def retrieve(self, request, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return Response(
            {"detail": "Method not allowed."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )
