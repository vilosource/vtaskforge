"""v2 serializers for TaskEvent entities."""
from rest_framework import serializers

from core.refs import ActorRefField, TaskRefSerializer
from .models import TaskEvent


class TaskEventV2Serializer(serializers.ModelSerializer):
    actor = ActorRefField(read_only=True)

    class Meta:
        model = TaskEvent
        fields = [
            "id", "task", "event_type", "data", "trigger_source",
            "actor", "timestamp",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.task:
            data["task"] = TaskRefSerializer(instance.task).data
        return data
