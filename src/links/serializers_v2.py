"""v2 serializers for Link entities.

The v2 Link serializer replaces source_type/source_id/source_title and
target_type/target_id/target_title with embedded polymorphic ref objects.
"""
from rest_framework import serializers

from core.refs import ActorRefField
from .models import Link


# Internal source types that get full entity refs
_INTERNAL_TYPES = {"task", "milestone", "workplan"}


def _resolve_entity_ref(entity_type, entity_id, cache=None):
    """Resolve an entity type + ID to a ref dict.

    For internal types (task, milestone, workplan), returns a typed ref.
    For external types, returns {type, id, label}.
    Uses cache dict if provided to avoid N+1 queries.
    """
    if entity_type in _INTERNAL_TYPES:
        entity = None
        if cache and entity_type in cache:
            entity = cache[entity_type].get(entity_id)

        if entity is None:
            entity = _fetch_entity(entity_type, entity_id)

        if entity is None:
            # Deleted entity — graceful degradation
            if entity_type == "task":
                return {"type": "task", "id": entity_id, "title": None, "status": None}
            elif entity_type == "milestone":
                return {"type": "milestone", "id": entity_id, "name": None, "status": None}
            else:
                return {"type": "workplan", "id": entity_id, "name": None}

        if entity_type == "task":
            return {"type": "task", "id": entity.id, "title": entity.title, "status": entity.status}
        elif entity_type == "milestone":
            return {"type": "milestone", "id": entity.id, "name": entity.name, "status": entity.status}
        else:
            return {"type": "workplan", "id": entity.id, "name": entity.name}

    # External type
    return {"type": entity_type, "id": entity_id, "label": entity_id}


def _fetch_entity(entity_type, entity_id):
    """Fetch a single entity by type and ID."""
    if entity_type == "task":
        from tasks.models import Task
        return Task.objects.filter(pk=entity_id).first()
    elif entity_type == "milestone":
        from workplans.models import Milestone
        return Milestone.objects.filter(pk=entity_id).first()
    elif entity_type == "workplan":
        from workplans.models import Workplan
        return Workplan.objects.filter(pk=entity_id).first()
    return None


def build_link_entity_cache(links):
    """Batch-fetch all referenced entities for a list of links.

    Returns a dict: {type_name: {entity_id: entity_instance}}
    """
    from tasks.models import Task
    from workplans.models import Milestone, Workplan

    ids_by_type = {"task": set(), "milestone": set(), "workplan": set()}

    for link in links:
        for etype, eid in [(link.source_type, link.source_id), (link.target_type, link.target_id)]:
            if etype in ids_by_type:
                ids_by_type[etype].add(eid)

    cache = {}
    if ids_by_type["task"]:
        cache["task"] = {t.id: t for t in Task.objects.filter(pk__in=ids_by_type["task"])}
    if ids_by_type["milestone"]:
        cache["milestone"] = {m.id: m for m in Milestone.objects.filter(pk__in=ids_by_type["milestone"])}
    if ids_by_type["workplan"]:
        cache["workplan"] = {w.id: w for w in Workplan.objects.filter(pk__in=ids_by_type["workplan"])}

    return cache


class LinkV2Serializer(serializers.ModelSerializer):
    source = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    created_by = ActorRefField(read_only=True)

    class Meta:
        model = Link
        fields = [
            "id", "source", "target", "link_type", "metadata",
            "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "created_by"]

    def get_source(self, obj):
        cache = self.context.get("entity_cache")
        return _resolve_entity_ref(obj.source_type, obj.source_id, cache)

    def get_target(self, obj):
        cache = self.context.get("entity_cache")
        return _resolve_entity_ref(obj.target_type, obj.target_id, cache)


class LinkV2WriteSerializer(serializers.ModelSerializer):
    """Write serializer for v2 links — accepts flat IDs, returns v2 shape."""

    class Meta:
        model = Link
        fields = [
            "id", "source_type", "source_id", "target_type", "target_id",
            "link_type", "metadata", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        """After create, return the v2 read shape."""
        return LinkV2Serializer(instance, context=self.context).data
