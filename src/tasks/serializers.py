from rest_framework import serializers

from .models import Task


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "phase",
            "workplan",
            "acceptance_criteria",
            "needs_review_before_start",
            "needs_review_on_completion",
            "review_return_to",
            "requires",
            "assigned_to",
            "claimed_by",
            "claimed_at",
            "claim_timeout",
            "claim_expires_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status"]
