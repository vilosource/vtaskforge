from rest_framework import serializers

from .models import Milestone, Workplan


class WorkplanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workplan
        fields = [
            "id",
            "name",
            "description",
            "status",
            "owner",
            "tags",
            "target_date",
            "default_needs_review_before_start",
            "default_needs_review_on_completion",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class MilestoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Milestone
        fields = [
            "id",
            "name",
            "description",
            "workplan",
            "status",
            "order",
            "default_needs_review_before_start",
            "default_needs_review_on_completion",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
