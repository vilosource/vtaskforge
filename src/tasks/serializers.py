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
            "project",
            "milestone",
            "workplan",
            "labels",
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
            "spec",
            "agent_model",
            "test_command",
            "judge",
            "isolation",
            "retry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "status", "retry_count"]

    def validate_acceptance_criteria(self, value):
        """Normalize acceptance_criteria to a list.

        Accepts a JSON array (pass-through) or a string (split on newlines,
        stripping leading '- ' markers).
        """
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [line.strip().lstrip("- ") for line in value.splitlines() if line.strip()]
        raise serializers.ValidationError("Must be a list or a string.")

    def validate_labels(self, value):
        """Normalize labels to a list of strings."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raise serializers.ValidationError("Must be a list or a comma-separated string.")

    def validate(self, data):
        """
        Validate task relationships:
        - project is required
        - workplan is optional
        - milestone is optional
        - If milestone is set, workplan must also be set
        - If milestone is set, milestone.workplan must equal workplan
        - If workplan is set, workplan.project must equal project
        - labels is optional, defaults to []
        """
        project = data.get('project')
        workplan = data.get('workplan')
        milestone = data.get('milestone')

        # For updates, get existing values if not in data
        if self.instance:
            project = project if project is not None else self.instance.project
            workplan = workplan if 'workplan' in data else self.instance.workplan
            milestone = milestone if 'milestone' in data else self.instance.milestone

        # project is always required
        if not project:
            raise serializers.ValidationError("project is required")

        # If milestone is set, workplan must also be set
        if milestone and not workplan:
            raise serializers.ValidationError("If milestone is set, workplan must also be set")

        # If milestone is set, milestone.workplan must equal workplan
        if milestone and workplan and milestone.workplan != workplan:
            raise serializers.ValidationError("milestone.workplan must equal workplan")

        # If workplan is set, workplan.project must equal project
        if workplan and workplan.project != project:
            raise serializers.ValidationError("workplan.project must equal project")

        # judge=True implies needs_review_on_completion=True
        judge = data.get('judge')
        review = data.get('needs_review_on_completion')

        # For updates, resolve current values
        if self.instance:
            judge = judge if 'judge' in data else self.instance.judge
            review = review if 'needs_review_on_completion' in data else self.instance.needs_review_on_completion

        if judge is True:
            if review is False:
                raise serializers.ValidationError(
                    "judge=True requires needs_review_on_completion to be True. "
                    "Cannot skip review when a judge is required."
                )
            if review is None:
                data['needs_review_on_completion'] = True

        return data


class TaskDetailSerializer(TaskSerializer):
    """Extended serializer for GET /v1/tasks/:id with optional ?expand= support.

    Fields links, reviews, and events are always present in the response but
    return None when the corresponding key is not in context['expand'].
    """

    links = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    traces = serializers.SerializerMethodField()

    class Meta(TaskSerializer.Meta):
        fields = TaskSerializer.Meta.fields + ["links", "reviews", "events", "traces"]

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

    def get_traces(self, obj):
        if not self._expand_requested("traces"):
            return None
        from tasks.cxdb import fetch_traces
        return fetch_traces(obj.id)
