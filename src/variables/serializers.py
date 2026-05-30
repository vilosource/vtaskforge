from rest_framework import serializers

from .models import ProjectVariable


class ProjectVariableSerializer(serializers.ModelSerializer):
    """Serializer for a project's secret-variable declaration.

    `project` is bound from the URL, not the body. `name`/`role` are writable on
    create but immutable thereafter (enforced in the viewset).
    """

    class Meta:
        model = ProjectVariable
        fields = [
            "id",
            "name",
            "role",
            "scope",
            "description",
            "required",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
