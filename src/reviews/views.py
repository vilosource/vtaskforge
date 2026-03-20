from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tasks.exceptions import InvalidTransition
from tasks.models import Task
from tasks.state_machine import perform_transition
from tasks.views import invalid_transition_response

from .models import Review
from .serializers import ReviewSerializer

REVIEW_STATUSES = {"pending_start_review", "pending_completion_review"}


class ReviewViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, GenericViewSet):
    serializer_class = ReviewSerializer

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
        if self.get_task() is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        task = self.get_task()
        if task is None:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if task.status not in REVIEW_STATUSES:
            return Response(
                {
                    "detail": (
                        f"Reviews can only be submitted when task is in a review state. "
                        f"Current status: '{task.status}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        decision = serializer.validated_data["decision"]

        try:
            if decision == "approved":
                if task.status == "pending_start_review":
                    perform_transition(task, "todo")
                else:  # pending_completion_review
                    perform_transition(task, "done")
            else:
                # rejected or changes_requested — set review_return_to BEFORE transitioning
                task.review_return_to = task.status
                task.save(update_fields=["review_return_to", "updated_at"])
                perform_transition(task, "changes_requested")
        except InvalidTransition as exc:
            return invalid_transition_response(exc)

        serializer.save(task=task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
