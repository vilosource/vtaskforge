from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from tasks.models import Task

from .models import Agent


class AgentSerializer(serializers.ModelSerializer):
    current_task = serializers.SerializerMethodField()
    tasks_completed = serializers.SerializerMethodField()
    tasks_failed = serializers.SerializerMethodField()
    effective_status = serializers.SerializerMethodField()

    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "tags",
            "status",
            "effective_status",
            "last_heartbeat",
            "pod_name",
            "registered_at",
            "created_at",
            "updated_at",
            "current_task",
            "tasks_completed",
            "tasks_failed",
        ]
        read_only_fields = ["id", "registered_at", "created_at", "updated_at"]

    def get_current_task(self, obj):
        task = Task.objects.filter(claimed_by=obj.id, status="doing").first()
        if task is None:
            return None
        return {"id": task.id, "title": task.title, "status": task.status}

    def get_tasks_completed(self, obj):
        return Task.objects.filter(claimed_by=obj.id, status="done").count()

    def get_tasks_failed(self, obj):
        return Task.objects.filter(claimed_by=obj.id, status="needs_attention").count()

    def get_effective_status(self, obj):
        if obj.status != "online":
            return obj.status
        threshold = getattr(settings, "AGENT_STALE_THRESHOLD_SECONDS", 300)
        if obj.last_heartbeat is None:
            return "stale"
        if (timezone.now() - obj.last_heartbeat).total_seconds() > threshold:
            return "stale"
        return "online"
