"""Authorization utilities for project-scoped access control."""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, SAFE_METHODS

from prefs.models import ProjectMembership


def scope_queryset_to_user_projects(qs, user, model_class):
    """Filter queryset to user's project memberships. Staff sees all."""
    if not user.is_authenticated:
        return qs.none()
    if user.is_staff:
        return qs
    filter_path = getattr(model_class, "project_filter_path", None)
    if filter_path is None:
        return qs
    user_project_ids = ProjectMembership.objects.filter(
        user=user
    ).values_list("project_id", flat=True)
    return qs.filter(**{f"{filter_path}__in": user_project_ids})


def check_project_membership(user, project_id: str) -> bool:
    """Return True if user is staff or has membership in the project."""
    if user.is_staff:
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
        if request.user.is_staff:
            return True
        project_id = getattr(obj, "get_project_id", lambda: None)()
        if project_id is None:
            return True
        return ProjectMembership.objects.filter(
            user=request.user, project_id=project_id
        ).exists()


class RoleBasedPermission(BasePermission):
    """Enforce owner/member/viewer roles on write operations."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        if request.method in SAFE_METHODS:
            return True
        project_id = getattr(obj, "get_project_id", lambda: None)()
        if project_id is None:
            return True
        membership = ProjectMembership.objects.filter(
            user=request.user, project_id=project_id
        ).first()
        if not membership:
            return False
        if membership.role == "owner":
            return True
        if membership.role == "viewer":
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
