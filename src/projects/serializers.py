from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    owner = serializers.SlugRelatedField(
        slug_field="username", read_only=True, allow_null=True,
    )
    created_by = serializers.SlugRelatedField(
        slug_field="username", read_only=True, allow_null=True,
    )

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "description",
            "status",
            "repo_url",
            "default_branch",
            "tags",
            "owner",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "owner", "created_by"]