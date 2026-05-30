from rest_framework import serializers

from .models import ProjectVariable, VariableAudit


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


class VariableAuditSerializer(serializers.ModelSerializer):
    """Forensic audit row written by the vafi controller per Vault read.

    Never carries the value/hash/prefix — the model has no such field.
    """

    class Meta:
        model = VariableAudit
        fields = [
            "audit_id",
            "timestamp",
            "task",
            "project",
            "variable_name",
            "variable_scope",
            "vault_path",
            "vault_version",
            "result",
            "size_bytes",
            "duration_ms",
            "controller_id",
            "created_at",
        ]
        read_only_fields = ["audit_id", "created_at"]
