"""v2 serializers for Workplan and Milestone entities."""
from rest_framework import serializers

from core.permissions_computer import compute_milestone_permissions, compute_workplan_permissions
from core.refs import ActorRefField, ProjectRefSerializer, WorkplanRefSerializer
from .models import Milestone, Workplan


class WorkplanV2Serializer(serializers.ModelSerializer):
    owner = ActorRefField(read_only=True)
    created_by = ActorRefField(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Workplan
        fields = [
            "id", "name", "description", "status", "project", "owner", "tags",
            "target_date", "default_needs_review_before_start",
            "default_needs_review_on_completion", "created_by",
            "created_at", "updated_at", "permissions",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at", "owner", "created_by",
            "permissions",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace bare project ID with ProjectRef on read
        if instance.project:
            data["project"] = ProjectRefSerializer(instance.project).data
        else:
            data["project"] = None
        return data

    def get_permissions(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return compute_workplan_permissions(obj, request.user)
        return None


class MilestoneV2Serializer(serializers.ModelSerializer):
    created_by = ActorRefField(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = [
            "id", "name", "description", "status", "order", "workplan",
            "default_needs_review_before_start",
            "default_needs_review_on_completion", "created_by",
            "created_at", "updated_at", "permissions",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at", "created_by",
            "permissions",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.workplan:
            data["workplan"] = WorkplanRefSerializer(instance.workplan).data
        else:
            data["workplan"] = None
        return data

    def get_permissions(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return compute_milestone_permissions(obj, request.user)
        return None
