"""DRF permissions for project-scoped access control."""

from rest_framework.permissions import BasePermission

from .models import ProjectMembership


class HasProjectMembership(BasePermission):
    """Check that the user has a membership for the project in the URL.

    Expects `project_id` in the view's URL kwargs.
    Staff users bypass the check.
    """

    def has_permission(self, request, view):
        if request.user.is_staff:
            return True

        project_id = view.kwargs.get("project_id") or view.kwargs.get("pk")
        if not project_id:
            return True  # No project scope — allow (e.g., list all projects)

        return ProjectMembership.objects.filter(
            user=request.user, project_id=project_id
        ).exists()
