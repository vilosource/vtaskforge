from rest_framework import mixins, status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from core.authorization import ProjectScopedPermission, RoleBasedPermission, require_project_membership
from rest_framework.permissions import IsAuthenticated
from tasks.exceptions import InvalidTransition
from tasks.models import Task
from tasks.serializers_v2 import TaskV2Serializer
from tasks.views import invalid_transition_response

from core.versioning import VersionedSerializerMixin
from .models import Review
from .serializers import ReviewSerializer
from .serializers_v2 import ReviewV2Serializer
from .services import ReviewError, submit_review


class ReviewViewSet(VersionedSerializerMixin, mixins.CreateModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = ReviewSerializer
    serializer_class_v2 = ReviewV2Serializer
    permission_classes = [IsAuthenticated, ProjectScopedPermission, RoleBasedPermission]

    def get_task(self):
        task_id = self.kwargs["task_id"]
        try:
            return Task.objects.get(pk=task_id)
        except Task.DoesNotExist:
            return None

    def get_queryset(self):
        task_id = self.kwargs["task_id"]
        return Review.objects.filter(task_id=task_id)

    def list(self, request, *args, **kwargs):
        task = self.get_task()
        if task is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        require_project_membership(request.user, task.project_id)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        task = self.get_task()
        if task is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        require_project_membership(request.user, task.project_id)

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        decision = serializer.validated_data["decision"]
        reason = serializer.validated_data.get("reason", "")
        reviewer_type = serializer.validated_data.get("reviewer_type", "human")

        try:
            result = submit_review(
                task_id=task.id,
                decision=decision,
                reason=reason,
                reviewer=request.user,
                reviewer_type=reviewer_type,
            )
        except ReviewError as exc:
            return Response({"detail": exc.message}, status=exc.status_code)
        except InvalidTransition as exc:
            return invalid_transition_response(exc)

        out_serializer = self.get_serializer(result["review"])
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)


class PendingReviewsView(ListAPIView):
    """GET /v2/reviews/pending/ — tasks awaiting judge completion review.

    Cross-project endpoint for judge-role agents. Returns tasks in
    `pending_completion_review` with `judge=True`, NOT scoped to the
    caller's project memberships — a fleet-wide judge sees every task
    that needs reviewing regardless of which project it lives in.

    This is the role-correct counterpart to filtering `/v1/tasks/` by
    status, which applies generic membership scoping and silently
    returns 0 for agents that haven't been added as project members.
    See vtaskforge#6 for the silent-fail incident that motivated this.

    v2-only by design — v1 is in deprecation.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TaskV2Serializer

    def get_queryset(self):
        return (
            Task.objects.select_related(
                "project", "milestone", "workplan",
                "assigned_to", "claimed_by", "created_by",
            )
            .filter(status="pending_completion_review", judge=True)
            .order_by("updated_at")
        )
