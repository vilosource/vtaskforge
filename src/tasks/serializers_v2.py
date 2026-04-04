"""v2 serializers for Task entities.

NoteV2Serializer is created in Step 6.
TaskV2Serializer and TaskDetailV2Serializer will be added in Step 8.
"""
from rest_framework import serializers

from core.refs import ActorRefField, TaskRefSerializer
from .models import Note


class NoteV2Serializer(serializers.ModelSerializer):
    actor = ActorRefField(read_only=True)

    class Meta:
        model = Note
        fields = ["id", "task", "text", "actor", "created_at"]
        read_only_fields = ["id", "task", "created_at", "actor"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.task:
            data["task"] = TaskRefSerializer(instance.task).data
        return data
