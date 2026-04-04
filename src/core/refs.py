"""Shared v2 reference serializers and fields.

These ref types are used by all v2 entity serializers to embed
entity references as typed objects instead of bare IDs.
"""
from rest_framework import serializers


class ProjectRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class WorkplanRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class MilestoneRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    status = serializers.CharField()


class TaskRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    title = serializers.CharField()
    status = serializers.CharField()


class ActorRefField(serializers.Field):
    """Resolves a User FK to a discriminated ActorRef object.

    Agent user -> {type: "agent", id, name, pod_name}
    Human user -> {type: "user", id, username}
    None       -> None
    """

    def to_representation(self, value):
        if value is None:
            return None
        # Check for Agent via OneToOne reverse relation
        agent = getattr(value, "agent", None)
        if agent is not None:
            return {
                "type": "agent",
                "id": str(agent.id),
                "name": agent.name,
                "pod_name": agent.pod_name,
            }
        return {
            "type": "user",
            "id": str(value.pk),
            "username": value.username,
        }

    def to_internal_value(self, data):
        raise NotImplementedError("ActorRefField is read-only")
