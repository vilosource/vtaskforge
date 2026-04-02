"""API views for user preferences."""

from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AgentLock, ChannelProjectMapping, ExternalIdentity, ProjectMembership, RecentAccess, SessionRecord
from .services import get_or_create_profile


class IsHumanUser(BasePermission):
    """Only allow users with a usable password (humans)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_usable_password()


class ExternalIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExternalIdentity
        fields = ["id", "provider", "external_id", "workspace_id", "linked_at"]
        read_only_fields = ["id", "linked_at"]


class SessionRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionRecord
        fields = [
            "id", "project_id", "role", "cxdb_context_id",
            "channel", "started_at", "ended_at", "summary",
        ]


class AgentLockSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AgentLock
        fields = ["id", "project_id", "role", "user", "session_id", "created_at", "last_activity"]
        read_only_fields = ["id", "user", "created_at", "last_activity"]


class ChannelProjectMappingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChannelProjectMapping
        fields = ["id", "provider", "channel_id", "channel_name", "project_id", "created_at"]
        read_only_fields = ["id", "created_at"]


class RecentAccessSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecentAccess
        fields = ["resource_type", "resource_id", "resource_title", "resource_status", "accessed_at"]


class RecentAccessView(APIView):
    """GET /v1/profile/recent/ — list recently accessed resources."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Reject agent users (no usable password)
        if not request.user.has_usable_password():
            return Response(
                {"detail": "Agent tokens cannot access user profile endpoints."},
                status=status.HTTP_403_FORBIDDEN,
            )

        accesses = RecentAccess.objects.filter(user=request.user)[:20]
        serializer = RecentAccessSerializer(accesses, many=True)
        return Response({"results": serializer.data})


class TokenValidationView(APIView):
    """GET /v1/auth/validate/ — validate token and return user identity."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = get_or_create_profile(request.user)
        memberships = ProjectMembership.objects.filter(user=request.user)
        projects = [
            {"project_id": m.project_id, "role": m.role}
            for m in memberships
        ]
        return Response({
            "user_id": request.user.pk,
            "username": request.user.username,
            "user_type": profile.user_type,
            "is_staff": request.user.is_staff,
            "projects": projects,
        })


class ExternalIdentityView(APIView):
    """GET/POST /v1/external-identities/ — manage linked external accounts."""

    permission_classes = [IsAuthenticated, IsHumanUser]

    def get(self, request):
        qs = ExternalIdentity.objects.filter(user=request.user)
        provider = request.query_params.get("provider")
        external_id = request.query_params.get("external_id")
        if provider:
            qs = qs.filter(provider=provider)
        if external_id:
            qs = qs.filter(external_id=external_id)
        serializer = ExternalIdentitySerializer(qs, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = ExternalIdentitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExternalIdentityDetailView(APIView):
    """DELETE /v1/external-identities/<pk>/ — remove a linked identity."""

    permission_classes = [IsAuthenticated, IsHumanUser]

    def delete(self, request, pk):
        try:
            identity = ExternalIdentity.objects.get(pk=pk, user=request.user)
        except ExternalIdentity.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        identity.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SessionHistoryView(APIView):
    """GET /v1/profile/sessions/ — list session history (read-only, humans only)."""

    permission_classes = [IsAuthenticated, IsHumanUser]

    def get(self, request):
        qs = SessionRecord.objects.filter(user=request.user)
        project = request.query_params.get("project")
        if project:
            qs = qs.filter(project_id=project)
        serializer = SessionRecordSerializer(qs, many=True)
        return Response({"results": serializer.data})


class LockView(APIView):
    """GET/POST /v1/locks/ — list and acquire agent locks."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = AgentLock.objects.all()
        project_id = request.query_params.get("project_id")
        if project_id:
            qs = qs.filter(project_id=project_id)
        serializer = AgentLockSerializer(qs, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        project_id = request.data.get("project_id")
        role = request.data.get("role")
        if not project_id or not role:
            return Response(
                {"detail": "project_id and role are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            existing = AgentLock.objects.get(project_id=project_id, role=role)
            if existing.user == request.user:
                # Reconnect — return existing lock
                serializer = AgentLockSerializer(existing)
                return Response(serializer.data)
            else:
                # Locked by another user
                return Response(
                    {
                        "detail": f"Locked by {existing.user.username}",
                        "locked_by": existing.user.username,
                        "since": existing.created_at.isoformat(),
                    },
                    status=status.HTTP_409_CONFLICT,
                )
        except AgentLock.DoesNotExist:
            lock = AgentLock.objects.create(
                project_id=project_id, role=role, user=request.user
            )
            serializer = AgentLockSerializer(lock)
            return Response(serializer.data)


class LockDetailView(APIView):
    """DELETE /v1/locks/<pk>/ — release a lock."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            lock = AgentLock.objects.get(pk=pk, user=request.user)
        except AgentLock.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        lock.delete()
        return Response(status=status.HTTP_200_OK)


class ChannelMappingView(APIView):
    """GET/POST /v1/channel-mappings/ — manage channel-to-project mappings."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ChannelProjectMapping.objects.all()
        provider = request.query_params.get("provider")
        channel_id = request.query_params.get("channel_id")
        if provider:
            qs = qs.filter(provider=provider)
        if channel_id:
            qs = qs.filter(channel_id=channel_id)
        serializer = ChannelProjectMappingSerializer(qs, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = ChannelProjectMappingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChannelMappingDetailView(APIView):
    """DELETE /v1/channel-mappings/<pk>/ — remove a mapping."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            mapping = ChannelProjectMapping.objects.get(pk=pk)
        except ChannelProjectMapping.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        mapping.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
