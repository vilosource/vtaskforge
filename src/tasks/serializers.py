from rest_framework import serializers

from .models import Note, Task


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ["id", "task", "text", "actor_id", "created_at"]
        read_only_fields = ["id", "task", "created_at"]


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "phase",
            "workplan",
            "acceptance_criteria",
            "needs_review_before_start",
            "needs_review_on_completion",
            "review_return_to",
            "requires",
            "assigned_to",
            "claimed_by",
            "claimed_at",
            "claim_timeout",
            "claim_expires_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status"]


class TaskDetailSerializer(TaskSerializer):
    """Extended serializer for GET /v1/tasks/:id with optional ?expand= support.

    Fields links, reviews, and events are always present in the response but
    return None when the corresponding key is not in context['expand'].
    """

    links = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["links", "reviews", "events"]

    def _expand_requested(self, field_name):
        expand = self.context.get("expand", [])
        return field_name in expand

    def get_links(self, obj):
        if not self._expand_requested("links"):
            return None
        from links.models import Link
        from links.serializers import LinkSerializer
        qs = Link.objects.filter(source_type="task", source_id=obj.id)
        return LinkSerializer(qs, many=True).data

    def get_reviews(self, obj):
        if not self._expand_requested("reviews"):
            return None
        from reviews.serializers import ReviewSerializer
        return ReviewSerializer(obj.reviews.all(), many=True).data

    def get_events(self, obj):
        if not self._expand_requested("events"):
            return None
        from events.serializers import TaskEventSerializer
        return TaskEventSerializer(obj.events.all(), many=True).data
