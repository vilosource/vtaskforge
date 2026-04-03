from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    # v1 backward compat: expose as "reviewer_id" with username string
    reviewer_id = serializers.SlugRelatedField(
        source="reviewer", slug_field="username", read_only=True, allow_null=True,
    )

    class Meta:
        model = Review
        fields = ["id", "task", "decision", "reason", "reviewer_id", "reviewer_type", "created_at", "updated_at"]
        read_only_fields = ["id", "task", "created_at", "updated_at", "reviewer_id"]
