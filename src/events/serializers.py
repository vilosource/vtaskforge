from rest_framework import serializers

from .models import TaskEvent


class TaskEventSerializer(serializers.ModelSerializer):
    triggered_by = serializers.SerializerMethodField()

    class Meta:
        model = TaskEvent
        fields = ["id", "task", "event_type", "data", "timestamp", "triggered_by"]
        read_only_fields = ["id", "task", "event_type", "data", "timestamp", "triggered_by"]

    def get_triggered_by(self, obj):
        """v1 backward compat: return triggered_by as a string.

        If actor FK is set, return the username. Otherwise return trigger_source.
        This preserves the old format for v1 consumers.
        """
        if obj.actor:
            return obj.actor.username
        return obj.trigger_source
