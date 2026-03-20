from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .models import Phase, Workplan
from .serializers import PhaseSerializer, WorkplanSerializer


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


class WorkplanPhasesView(APIView):
    """Nested endpoint: list and create phases under a workplan."""

    def get_workplan(self, workplan_id):
        try:
            return Workplan.objects.get(pk=workplan_id)
        except Workplan.DoesNotExist:
            return None

    def get(self, request, workplan_id):
        workplan = self.get_workplan(workplan_id)
        if workplan is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        phases = Phase.objects.filter(workplan=workplan)
        serializer = PhaseSerializer(phases, many=True)
        return Response(serializer.data)

    def post(self, request, workplan_id):
        workplan = self.get_workplan(workplan_id)
        if workplan is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data["workplan"] = workplan.id
        serializer = PhaseSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PhaseViewSet(ModelViewSet):
    queryset = Phase.objects.all()
    serializer_class = PhaseSerializer
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
        phase = self.get_object()
        if phase.status != "pending":
            return Response(
                {"detail": "Only pending phases can be activated."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        phase.status = "active"
        phase.save()
        serializer = self.get_serializer(phase)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        phase = self.get_object()
        if phase.status != "active":
            return Response(
                {"detail": "Only active phases can be completed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        phase.status = "completed"
        phase.save()
        serializer = self.get_serializer(phase)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def stats(self, request, pk=None):
        phase = self.get_object()
        stats_data = {
            "phase_id": phase.id,
            "total_tasks": 0,
            "completed_tasks": 0,
            "pending_tasks": 0,
            "in_progress_tasks": 0,
        }
        return Response(stats_data)
