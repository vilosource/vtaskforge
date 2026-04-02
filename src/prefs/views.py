"""API views for user preferences."""

from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework import serializers, status
from rest_framework.permissions import BasePermission, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AgentLock, ChannelProjectMapping, ExternalIdentity, ProjectMembership, RecentAccess, SessionRecord
from .services import (
    LockConflict,
    acquire_lock,
    create_service_account,
    get_or_create_profile,
    list_locks,
    release_lock,
    update_user_type,
)


class IsHumanUser(BasePermission):
    """Only allow users with a usable password (humans)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_usable_password()


class IsAgentOrStaff(BasePermission):
    """Allow agent users (no usable password) and staff."""

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True
        return not request.user.has_usable_password()  # agent user


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

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAgentOrStaff()]
        return [IsAuthenticated()]

    def get(self, request):
        project_id = request.query_params.get("project_id")
        locks = list_locks(project_id=project_id)
        serializer = AgentLockSerializer(locks, many=True)
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
            lock = acquire_lock(
                request.user,
                project_id,
                role,
                session_id=request.data.get("session_id", ""),
            )
            serializer = AgentLockSerializer(lock)
            return Response(serializer.data)
        except LockConflict as e:
            return Response(
                {
                    "detail": f"Locked by {e.lock.user.username}",
                    "locked_by": e.lock.user.username,
                    "since": e.lock.created_at.isoformat(),
                },
                status=status.HTTP_409_CONFLICT,
            )


class LockDetailView(APIView):
    """DELETE /v1/locks/<pk>/ — release a lock."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            release_lock(pk, request.user, force=request.user.is_staff)
        except AgentLock.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except PermissionError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_200_OK)


class ChannelMappingView(APIView):
    """GET/POST /v1/channel-mappings/ — manage channel-to-project mappings."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

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

    permission_classes = [IsAuthenticated, IsAdminUser]

    def delete(self, request, pk):
        try:
            mapping = ChannelProjectMapping.objects.get(pk=pk)
        except ChannelProjectMapping.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        mapping.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# User list / detail (staff only)
# ---------------------------------------------------------------------------


class ProjectMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)

    class Meta:
        model = ProjectMembership
        fields = ["id", "user_id", "username", "project_id", "role", "created_at"]
        read_only_fields = ["id", "user_id", "username", "created_at"]


class UserListSerializer(serializers.ModelSerializer):
    user_type = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "is_staff", "is_active", "user_type", "date_joined", "last_login"]

    def get_user_type(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.user_type if profile else "human"


class UserDetailSerializer(UserListSerializer):
    memberships = ProjectMembershipSerializer(source="project_memberships", many=True, read_only=True)

    class Meta(UserListSerializer.Meta):
        fields = UserListSerializer.Meta.fields + ["memberships"]


class UserListView(APIView):
    """GET /v1/users/ — list users with profile info (staff only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        from .services import list_users
        search = request.query_params.get("search")
        user_type = request.query_params.get("user_type")
        users = list_users(search=search, user_type=user_type)
        serializer = UserListSerializer(users, many=True)
        return Response({"results": serializer.data})


class UserDetailView(APIView):
    """GET/PATCH /v1/users/<pk>/ — user detail and update (staff only)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, pk):
        from .services import get_user_detail
        try:
            user = get_user_detail(pk)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = UserDetailSerializer(user)
        return Response(serializer.data)

    def patch(self, request, pk):
        user_type = request.data.get("user_type")
        if not user_type:
            return Response(
                {"detail": "user_type is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            profile = update_user_type(pk, user_type)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        # Re-fetch full user for serialization
        from .services import get_user_detail
        user = get_user_detail(pk)
        serializer = UserDetailSerializer(user)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Service account creation (staff only)
# ---------------------------------------------------------------------------


class ServiceAccountView(APIView):
    """POST /v1/service-accounts/ — create service account, return user + token."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        name = request.data.get("name")
        if not name:
            return Response(
                {"detail": "name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            user, token = create_service_account(name)
        except IntegrityError:
            return Response(
                {"detail": f"User '{name}' already exists."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "id": user.pk,
                "username": user.username,
                "token": token.key,
                "user_type": "service",
            },
            status=status.HTTP_201_CREATED,
        )
