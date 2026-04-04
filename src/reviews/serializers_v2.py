"""v2 serializers for Review entities."""
from rest_framework import serializers

from core.refs import ActorRefField, TaskRefSerializer
from .models import Review


class ReviewV2Serializer(serializers.ModelSerializer):
    reviewer = ActorRefField(read_only=True)
    permissions = None  # Reviews don't have permissions

    class Meta:
        model = Review
        fields = [
            "id", "task", "decision", "reason", "reviewer",
            "reviewer_type", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "task", "created_at", "updated_at", "reviewer"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.task:
            data["task"] = TaskRefSerializer(instance.task).data
        return data
