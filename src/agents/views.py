from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.pagination import VTFAgentCursorPagination, VTFCursorPagination
from tasks.models import Task
from tasks.serializers import TaskSerializer

from core.versioning import VersionedSerializerMixin
from .models import Agent
from .serializers import AgentSerializer
from .serializers_v2 import AgentV2Serializer


class AgentViewSet(VersionedSerializerMixin, ModelViewSet):
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
    serializer_class_v2 = AgentV2Serializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    pagination_class = VTFAgentCursorPagination

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(status="online")

    def create(self, request, *args, **kwargs):
        name = request.data.get("name")

        # Upsert: if agent with this name exists, update and return existing token
        if name:
            existing = Agent.objects.filter(name=name).first()
            if existing:
                serializer = self.get_serializer(existing, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)
                existing.status = "online"
                existing.save(update_fields=["status", "updated_at"])
                serializer.save()

                user = User.objects.get(username=existing.id)
                token = Token.objects.get(user=user)

                # Ensure Agent.user FK is set (backfill for pre-FK agents)
                if not existing.user_id:
                    existing.user = user
                    existing.save(update_fields=["user"])

                data = serializer.data
                data["token"] = token.key
                return Response(data, status=status.HTTP_200_OK)

        # New agent: create agent, user, and token
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        agent = serializer.instance

        user = User.objects.create_user(username=agent.id)
        token = Token.objects.create(user=user)

        # Link Agent → User via FK
        agent.user = user
        agent.save(update_fields=["user"])

        data = serializer.data
        data["token"] = token.key
        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        # Disable full PUT — PATCH only
        if not kwargs.get("partial", False):
            return Response(
                {"detail": "Method not allowed. Use PATCH for partial updates."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        agent = self.get_object()
        qs = Task.objects.filter(claimed_by=agent.user).order_by("-updated_at")

        task_status = request.query_params.get("status")
        if task_status:
            qs = qs.filter(status=task_status)

        paginator = VTFCursorPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = TaskSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
