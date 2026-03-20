from rest_framework import serializers

from .models import Link


class LinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Link
        fields = [
            "id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "link_type",
            "metadata",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
