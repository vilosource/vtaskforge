"""v2 serializers for prefs entities (Lock, ChannelMapping, User, Membership)."""
from django.contrib.auth.models import User
from rest_framework import serializers

from core.refs import ActorRefField, ProjectRefSerializer
from prefs.models import AgentLock, ChannelProjectMapping, ProjectMembership


class AgentLockV2Serializer(serializers.ModelSerializer):
    user = ActorRefField(read_only=True)
    project = serializers.SerializerMethodField()

    class Meta:
        model = AgentLock
        fields = ["id", "project", "role", "user", "session_id", "created_at", "last_activity"]
        read_only_fields = ["id", "user", "created_at", "last_activity"]

    def get_project(self, obj):
        if obj.project_id:
            from projects.models import Project
            try:
                project = Project.objects.get(pk=obj.project_id)
                return ProjectRefSerializer(project).data
            except Project.DoesNotExist:
                return {"id": obj.project_id, "name": None}
        return None


class ChannelProjectMappingV2Serializer(serializers.ModelSerializer):
    project = serializers.SerializerMethodField()

    class Meta:
        model = ChannelProjectMapping
        fields = ["id", "provider", "channel_id", "channel_name", "project", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_project(self, obj):
        if obj.project_id:
            from projects.models import Project
            try:
                project = Project.objects.get(pk=obj.project_id)
                return ProjectRefSerializer(project).data
            except Project.DoesNotExist:
                return {"id": obj.project_id, "name": None}
        return None


class ProjectMembershipV2Serializer(serializers.ModelSerializer):
    user = ActorRefField(read_only=True)
    project = serializers.SerializerMethodField()

    class Meta:
        model = ProjectMembership
        fields = ["id", "user", "project", "role", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def get_project(self, obj):
        if obj.project_id:
            from projects.models import Project
            try:
                project = Project.objects.get(pk=obj.project_id)
                return ProjectRefSerializer(project).data
            except Project.DoesNotExist:
                return {"id": obj.project_id, "name": None}
        return None


class UserListV2Serializer(serializers.ModelSerializer):
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "is_staff", "is_active", "user_type", "date_joined", "last_login"]

    def get_user_type(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.user_type if profile else "human"


class UserDetailV2Serializer(UserListV2Serializer):
    memberships = ProjectMembershipV2Serializer(source="project_memberships", many=True, read_only=True)

    class Meta(UserListV2Serializer.Meta):
        fields = UserListV2Serializer.Meta.fields + ["memberships"]
