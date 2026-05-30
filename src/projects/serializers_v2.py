"""v2 serializers for Project entities."""
from rest_framework import serializers

from core.permissions_computer import compute_project_permissions
from core.refs import ActorRefField
from .models import Project


class ProjectV2Serializer(serializers.ModelSerializer):
    owner = ActorRefField(read_only=True)
    created_by = ActorRefField(read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "slug", "name", "description", "status", "repo_url",
            "default_branch", "tags", "owner", "created_by",
            "created_at", "updated_at", "permissions",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "owner", "created_by", "permissions"]

    def get_permissions(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return compute_project_permissions(obj, request.user)
        return None
