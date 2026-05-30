"""v2 serializers for Task entities."""
from rest_framework import serializers

from core.permissions_computer import compute_task_permissions
from core.refs import (
    ActorRefField,
    MilestoneRefSerializer,
    ProjectRefSerializer,
    TaskRefSerializer,
    WorkplanRefSerializer,
)
from .models import Note, Task


class NoteV2Serializer(serializers.ModelSerializer):
    actor = ActorRefField(read_only=True)

    class Meta:
        model = Note
        fields = ["id", "task", "text", "actor", "created_at"]
        read_only_fields = ["id", "task", "created_at", "actor"]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.task:
            data["task"] = TaskRefSerializer(instance.task).data
        return data


class TaskV2Serializer(serializers.ModelSerializer):
    """v2 Task serializer with embedded refs and permissions."""

    assigned_to = ActorRefField(read_only=True)
    claimed_by = ActorRefField(read_only=True)
    created_by = ActorRefField(read_only=True)
    permissions = serializers.SerializerMethodField()
    # WC-1/C2: server-derived base_ref. The rule lives in the SoR; the
    # controller consumes this and never re-derives it.
    base_ref = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id", "title", "description", "status",
            "project", "workplan", "milestone", "base_ref",
            "labels", "acceptance_criteria",
            "needs_review_before_start", "needs_review_on_completion",
            "review_return_to", "requires", "required_tags",
            "assigned_to", "claimed_by", "claimed_at",
            "claim_timeout", "claim_expires_at",
            "created_by", "spec", "variables", "agent_model",
            "test_command", "judge", "isolation",
            "retry_count", "execution_summary",
            "created_at", "updated_at", "permissions",
        ]
        read_only_fields = [
            "id", "created_at", "updated_at", "status", "retry_count",
            "created_by", "claimed_by", "permissions", "base_ref",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Replace FK IDs with embedded refs
        if instance.project:
            data["project"] = ProjectRefSerializer(instance.project).data
        else:
            data["project"] = None
        if instance.workplan:
            data["workplan"] = WorkplanRefSerializer(instance.workplan).data
        else:
            data["workplan"] = None
        if instance.milestone:
            data["milestone"] = MilestoneRefSerializer(instance.milestone).data
        else:
            data["milestone"] = None
        # `required_tags` is the list of agent capability tag strings — the
        # claiming agent's tags must be a superset. `requires` is reserved
        # for task-to-task dependency refs. See migration 0014 for the
        # split rationale and the find_claimable_tasks filter in
        # services.py.
        data["requires"] = list(instance.requires or [])
        data["required_tags"] = list(instance.required_tags or [])
        return data

    def get_base_ref(self, obj):
        from tasks.services import resolve_base_ref
        return resolve_base_ref(obj)

    def get_permissions(self, obj):
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user.is_authenticated:
            return compute_task_permissions(obj, request.user)
        return None

    def validate_acceptance_criteria(self, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [line.strip().lstrip("- ") for line in value.splitlines() if line.strip()]
        raise serializers.ValidationError("Must be a list or a string.")

    def validate_labels(self, value):
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raise serializers.ValidationError("Must be a list or a comma-separated string.")

    def validate(self, data):
        """Same validation as v1 — project required, milestone implies workplan, etc."""
        project = data.get('project')
        workplan = data.get('workplan')
        milestone = data.get('milestone')

        if self.instance:
            project = project if project is not None else self.instance.project
            workplan = workplan if 'workplan' in data else self.instance.workplan
            milestone = milestone if 'milestone' in data else self.instance.milestone

        if not project:
            raise serializers.ValidationError("project is required")

        if milestone and not workplan:
            raise serializers.ValidationError("If milestone is set, workplan must also be set")

        if milestone and workplan and milestone.workplan != workplan:
            raise serializers.ValidationError("milestone.workplan must equal workplan")

        if workplan and workplan.project != project:
            raise serializers.ValidationError("workplan.project must equal project")

        judge = data.get('judge')
        review = data.get('needs_review_on_completion')
        if self.instance:
            judge = judge if 'judge' in data else self.instance.judge
            review = review if 'needs_review_on_completion' in data else self.instance.needs_review_on_completion

        if judge is True:
            if review is False:
                raise serializers.ValidationError(
                    "judge=True requires needs_review_on_completion to be True."
                )
            if review is None:
                data['needs_review_on_completion'] = True

        # Variables substrate admission (parity with v1).
        if 'variables' in data:
            from variables.admission import validate_task_variables
            errors = validate_task_variables(data.get('variables'), project)
            if errors:
                raise serializers.ValidationError({"variables": errors})

        return data


class TaskDetailV2Serializer(TaskV2Serializer):
    """Extended v2 serializer with ?expand= support using v2 nested serializers."""

    links = serializers.SerializerMethodField()
    reviews = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()
    traces = serializers.SerializerMethodField()

    class Meta(TaskV2Serializer.Meta):
        fields = TaskV2Serializer.Meta.fields + ["links", "reviews", "events", "traces"]

    def _expand_requested(self, field_name):
        expand = self.context.get("expand", [])
        return field_name in expand

    def get_links(self, obj):
        if not self._expand_requested("links"):
            return None
        from links.models import Link
        from links.serializers_v2 import LinkV2Serializer
        qs = Link.objects.filter(source_type="task", source_id=obj.id)
        return LinkV2Serializer(qs, many=True, context=self.context).data

    def get_reviews(self, obj):
        if not self._expand_requested("reviews"):
            return None
        from reviews.serializers_v2 import ReviewV2Serializer
        return ReviewV2Serializer(obj.reviews.all(), many=True, context=self.context).data

    def get_events(self, obj):
        if not self._expand_requested("events"):
            return None
        from events.serializers_v2 import TaskEventV2Serializer
        return TaskEventV2Serializer(obj.events.all(), many=True, context=self.context).data

    def get_traces(self, obj):
        if not self._expand_requested("traces"):
            return None
        from tasks.cxdb import fetch_traces
        return fetch_traces(obj.id)
