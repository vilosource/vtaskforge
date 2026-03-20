from rest_framework import serializers

from .models import Agent


class AgentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Agent
        fields = [
            "id",
            "name",
            "tags",
            "status",
            "last_heartbeat",
            "registered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "registered_at", "created_at", "updated_at"]
