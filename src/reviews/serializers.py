from rest_framework import serializers

from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "task", "decision", "reason", "reviewer_id", "reviewer_type", "created_at", "updated_at"]
        read_only_fields = ["id", "task", "created_at", "updated_at"]
