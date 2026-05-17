"""Authorization utilities for project-scoped access control."""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, SAFE_METHODS

from prefs.models import ProjectMembership, UserProfile


def is_fleet_principal(user) -> bool:
    """A fleet service principal — authenticated + UserProfile.user_type
    == 'service'. Authorised by fleet role across the whole instance
    (scope S1), with NO ProjectMembership row: fleet agents are
    deployment infrastructure serving every project, not project
    collaborators. See vtaskforge/docs/fleet-principal-authorization-DESIGN.md
    (architecture R2, Bet B). Humans are unaffected.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return UserProfile.objects.filter(user=user, user_type="service").exists()


def scope_queryset_to_user_projects(qs, user, model_class):
    """Filter queryset to user's project memberships. Staff and fleet
    principals see all (the latter by instance-wide role)."""
    if not user.is_authenticated:
        return qs.none()
    if user.is_staff or is_fleet_principal(user):
        return qs
    filter_path = getattr(model_class, "project_filter_path", None)
    if filter_path is None:
        return qs
    user_project_ids = ProjectMembership.objects.filter(
        user=user
    ).values_list("project_id", flat=True)
    return qs.filter(**{f"{filter_path}__in": user_project_ids})


def check_project_membership(user, project_id: str) -> bool:
    """True if user is staff, a fleet principal, or a project member."""
    if user.is_staff or is_fleet_principal(user):
        return True
    return ProjectMembership.objects.filter(
        user=user, project_id=project_id
    ).exists()


def require_project_membership(user, project_id: str):
    """Raise PermissionDenied if user is not a member of the project."""
    if not check_project_membership(user, project_id):
        raise PermissionDenied("You are not a member of this project.")


class ProjectScopedPermission(BasePermission):
    """Object-level permission via obj.get_project_id()."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or is_fleet_principal(request.user):
            return True
        project_id = getattr(obj, "get_project_id", lambda: None)()
        if project_id is None:
            return True
        return ProjectMembership.objects.filter(
            user=request.user, project_id=project_id
        ).exists()


class RoleBasedPermission(BasePermission):
    """Enforce owner/member/viewer roles on write operations.

    A fleet principal is bounded to **member-equivalent** capability
    instance-wide: it may create and update its own/claimed objects but
    NOT delete, and gets no owner-only escalation and no membership-admin
    (those stay staff/owner). This is exactly what executor (claim +
    own-task writes) and judge (review writes) need and nothing more
    (scope S1; finer per-tag bounding is YAGNI / future S3).
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True
        project_id = getattr(obj, "get_project_id", lambda: None)()
        if project_id is None:
            return True

        if is_fleet_principal(request.user):
            role = "member"  # bounded; no membership row, no owner ops
        else:
            membership = ProjectMembership.objects.filter(
                user=request.user, project_id=project_id
            ).first()
            if not membership:
                return False
            role = membership.role

        if role == "owner":
            return True
        if role == "viewer":
            return False
        # member: can create, can update own, cannot delete.
        # An agent that claimed a task is also considered "own" for the
        # lifetime of the claim — this is how the vafi controller writes
        # execution_summary, heartbeats, and other post-execution metadata
        # back through the generic PATCH path.
        if request.method == "DELETE":
            return False
        if request.method in ("PATCH", "PUT"):
            created_by_id = getattr(obj, "created_by_id", None)
            claimed_by_id = getattr(obj, "claimed_by_id", None)
            if created_by_id and created_by_id != request.user.id:
                if claimed_by_id != request.user.id:
                    return False
        return True
