from rest_framework import mixins, status
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from tasks.exceptions import InvalidTransition
from tasks.models import Task
from tasks.views import invalid_transition_response

from .models import Review
from .serializers import ReviewSerializer
from .services import ReviewError, submit_review


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
