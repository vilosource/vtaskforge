"""Compute server-side permissions objects for v2 API responses.

Given an entity and a user, returns a dict describing what the
authenticated user can do. Reuses existing ProjectMembership roles
and the task state machine.
"""
from prefs.models import ProjectMembership
from tasks.state_machine import get_valid_transitions


def _get_role(user, project_id):
    """Return the user's role in the project, or None if not a member."""
    if user.is_staff:
        return "staff"
    membership = ProjectMembership.objects.filter(
        user=user, project_id=project_id,
    ).first()
    return membership.role if membership else None


def _is_owner_or_staff(role):
    return role in ("owner", "staff")


def compute_task_permissions(task, user):
    """Compute permissions for a Task entity."""
    role = _get_role(user, task.project_id)

    if role is None:
        return {"can_edit": False, "can_delete": False, "available_actions": []}

    is_owner_staff = _is_owner_or_staff(role)
    is_creator = task.created_by_id == user.pk

    if role == "viewer":
        return {"can_edit": False, "can_delete": False, "available_actions": []}

    # available_actions: state machine transitions available to this user
    # Owners/staff get all transitions, members get transitions only if they can edit
    transitions = get_valid_transitions(task.status)
    if is_owner_staff:
        available_actions = list(transitions)
    elif role == "member" and is_creator:
        available_actions = list(transitions)
    else:
        available_actions = []

    return {
        "can_edit": is_owner_staff or (role == "member" and is_creator),
        "can_delete": is_owner_staff,
        "available_actions": available_actions,
    }


def compute_project_permissions(project, user):
    """Compute permissions for a Project entity."""
    role = _get_role(user, project.id)

    if role is None:
        return {
            "can_edit": False,
            "can_delete": False,
            "can_archive": False,
            "can_manage_members": False,
        }

    is_owner_staff = _is_owner_or_staff(role)

    return {
        "can_edit": is_owner_staff or role == "member",
        "can_delete": is_owner_staff,
        "can_archive": is_owner_staff,
        "can_manage_members": is_owner_staff,
    }


def compute_workplan_permissions(workplan, user):
    """Compute permissions for a Workplan entity."""
    role = _get_role(user, workplan.project_id)

    if role is None:
        return {
            "can_edit": False,
            "can_delete": False,
            "can_archive": False,
            "can_complete": False,
        }

    is_owner_staff = _is_owner_or_staff(role)
    is_creator = workplan.created_by_id == user.pk

    return {
        "can_edit": is_owner_staff or (role == "member" and is_creator),
        "can_delete": is_owner_staff,
        "can_archive": is_owner_staff,
        "can_complete": is_owner_staff,
    }


def compute_milestone_permissions(milestone, user):
    """Compute permissions for a Milestone entity."""
    role = _get_role(user, milestone.workplan.project_id)

    if role is None:
        return {
            "can_edit": False,
            "can_delete": False,
            "can_activate": False,
            "can_complete": False,
        }

    is_owner_staff = _is_owner_or_staff(role)
    is_creator = milestone.created_by_id == user.pk

    can_activate = is_owner_staff and milestone.status == "pending"
    can_complete = is_owner_staff and milestone.status == "active"

    return {
        "can_edit": is_owner_staff or (role == "member" and is_creator),
        "can_delete": is_owner_staff,
        "can_activate": can_activate,
        "can_complete": can_complete,
    }
