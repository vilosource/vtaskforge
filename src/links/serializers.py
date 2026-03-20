from rest_framework import serializers

from .models import Link


class LinkSerializer(serializers.ModelSerializer):
    target_title = serializers.SerializerMethodField()
    source_title = serializers.SerializerMethodField()

    class Meta:
        model = Link
        fields = [
            "id",
            "source_type",
            "source_id",
            "source_title",
            "target_type",
            "target_id",
            "target_title",
            "link_type",
            "metadata",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_target_title(self, obj):
        if obj.target_type == "task":
            from tasks.models import Task
            try:
                return Task.objects.values_list("title", flat=True).get(pk=obj.target_id)
            except Task.DoesNotExist:
                return None
        if obj.target_type == "phase":
            from workplans.models import Phase
            try:
                return Phase.objects.values_list("name", flat=True).get(pk=obj.target_id)
            except Phase.DoesNotExist:
                return None
        if obj.target_type == "workplan":
            from workplans.models import Workplan
            try:
                return Workplan.objects.values_list("name", flat=True).get(pk=obj.target_id)
            except Workplan.DoesNotExist:
                return None
        return None

    def get_source_title(self, obj):
        if obj.source_type == "task":
            from tasks.models import Task
            try:
                return Task.objects.values_list("title", flat=True).get(pk=obj.source_id)
            except Task.DoesNotExist:
                return None
        if obj.source_type == "phase":
            from workplans.models import Phase
            try:
                return Phase.objects.values_list("name", flat=True).get(pk=obj.source_id)
            except Phase.DoesNotExist:
                return None
        if obj.source_type == "workplan":
            from workplans.models import Workplan
            try:
                return Workplan.objects.values_list("name", flat=True).get(pk=obj.source_id)
            except Workplan.DoesNotExist:
                return None
        return None
