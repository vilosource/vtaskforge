from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Agent
from .serializers import AgentSerializer


class AgentViewSet(ModelViewSet):
    queryset = Agent.objects.all()
    serializer_class = AgentSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(status="online")

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
