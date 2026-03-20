from rest_framework import serializers

from .models import TaskEvent


class TaskEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskEvent
        fields = ["id", "task", "event_type", "data", "timestamp", "triggered_by"]
        read_only_fields = ["id", "task", "event_type", "data", "timestamp", "triggered_by"]
