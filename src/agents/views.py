from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from core.pagination import VTFAgentCursorPagination

from .models import Agent
from .serializers import AgentSerializer


class AgentViewSet(ModelViewSet):
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
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
        # Validates agent exists (raises 404 if not found)
        self.get_object()
        # Placeholder — task assignment will be populated in later tasks
        return Response([])
