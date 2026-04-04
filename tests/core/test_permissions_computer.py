"""Step 4: Permissions computer tests.

Tests that compute_*_permissions returns correct permissions based on
user role, entity ownership, and state machine status.
"""
import pytest


@pytest.fixture
def users(db):
    from django.contrib.auth.models import User
    owner = User.objects.create_user("owner", password="pass")
    member = User.objects.create_user("member", password="pass")
    viewer = User.objects.create_user("viewer", password="pass")
    outsider = User.objects.create_user("outsider", password="pass")
    staff = User.objects.create_user("staffuser", password="pass", is_staff=True)
    return owner, member, viewer, outsider, staff


@pytest.fixture
def project_with_members(users):
    from projects.models import Project
    from prefs.models import ProjectMembership

    owner, member, viewer, outsider, staff = users
    project = Project.objects.create(name="PermTest", owner=owner, created_by=owner)
    ProjectMembership.objects.create(user=owner, project_id=project.id, role="owner")
    ProjectMembership.objects.create(user=member, project_id=project.id, role="member")
    ProjectMembership.objects.create(user=viewer, project_id=project.id, role="viewer")
    return project, users


@pytest.fixture
def task_in_project(project_with_members):
    from tasks.models import Task
    project, users = project_with_members
    owner = users[0]
    task = Task.objects.create(title="PermTask", project=project, created_by=owner, status="draft")
    return task, project, users


class TestTaskPermissions:

    def test_task_perms_owner(self, task_in_project):
        """DoD #1"""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        owner = users[0]
        perms = compute_task_permissions(task, owner)
        assert perms["can_edit"] is True
        assert perms["can_delete"] is True

    def test_task_perms_member_own(self, task_in_project):
        """DoD #2: Member who created the task."""
        from core.permissions_computer import compute_task_permissions
        from tasks.models import Task
        task, project, users = task_in_project
        member = users[1]
        # Create a task owned by the member
        member_task = Task.objects.create(title="MemberTask", project=project, created_by=member)
        perms = compute_task_permissions(member_task, member)
        assert perms["can_edit"] is True
        assert perms["can_delete"] is False

    def test_task_perms_member_other(self, task_in_project):
        """DoD #3: Member who didn't create the task."""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        member = users[1]
        perms = compute_task_permissions(task, member)
        assert perms["can_edit"] is False
        assert perms["can_delete"] is False

    def test_task_perms_viewer(self, task_in_project):
        """DoD #4"""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        viewer = users[2]
        perms = compute_task_permissions(task, viewer)
        assert perms["can_edit"] is False
        assert perms["can_delete"] is False
        assert perms["available_actions"] == []

    def test_task_perms_staff(self, task_in_project):
        """DoD #5"""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        staff = users[4]
        perms = compute_task_permissions(task, staff)
        assert perms["can_edit"] is True
        assert perms["can_delete"] is True
        assert len(perms["available_actions"]) > 0

    def test_task_actions_draft(self, task_in_project):
        """DoD #6"""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        owner = users[0]
        assert task.status == "draft"
        perms = compute_task_permissions(task, owner)
        actions = perms["available_actions"]
        assert "todo" in actions
        assert "cancelled" in actions
        assert "deferred" in actions

    def test_task_actions_done(self, task_in_project):
        """DoD #7"""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        owner = users[0]
        task.status = "done"
        task.save(update_fields=["status"])
        perms = compute_task_permissions(task, owner)
        assert perms["available_actions"] == []

    def test_task_actions_doing_owner(self, task_in_project):
        """DoD #8"""
        from core.permissions_computer import compute_task_permissions
        task, project, users = task_in_project
        owner = users[0]
        task.status = "doing"
        task.save(update_fields=["status"])
        perms = compute_task_permissions(task, owner)
        actions = perms["available_actions"]
        assert "done" in actions or "pending_completion_review" in actions
        assert "needs_attention" in actions
        assert "blocked" in actions


class TestProjectPermissions:

    def test_project_perms_owner(self, project_with_members):
        """DoD #9"""
        from core.permissions_computer import compute_project_permissions
        project, users = project_with_members
        owner = users[0]
        perms = compute_project_permissions(project, owner)
        assert perms["can_manage_members"] is True

    def test_project_perms_member(self, project_with_members):
        """DoD #10"""
        from core.permissions_computer import compute_project_permissions
        project, users = project_with_members
        member = users[1]
        perms = compute_project_permissions(project, member)
        assert perms["can_manage_members"] is False


class TestWorkplanMilestonePermissions:

    def test_workplan_perms_owner(self, project_with_members):
        """DoD #11"""
        from core.permissions_computer import compute_workplan_permissions
        from workplans.models import Workplan
        project, users = project_with_members
        owner = users[0]
        wp = Workplan.objects.create(name="WP", project=project, owner=owner, created_by=owner)
        perms = compute_workplan_permissions(wp, owner)
        assert perms["can_archive"] is True
        assert perms["can_complete"] is True

    def test_milestone_perms_active(self, project_with_members):
        """DoD #12"""
        from core.permissions_computer import compute_milestone_permissions
        from workplans.models import Workplan, Milestone
        project, users = project_with_members
        owner = users[0]
        wp = Workplan.objects.create(name="WP2", project=project, owner=owner, created_by=owner)
        ms = Milestone.objects.create(name="MS", workplan=wp, status="active", created_by=owner)
        perms = compute_milestone_permissions(ms, owner)
        assert perms["can_complete"] is True

    def test_milestone_perms_pending(self, project_with_members):
        """DoD #13"""
        from core.permissions_computer import compute_milestone_permissions
        from workplans.models import Workplan, Milestone
        project, users = project_with_members
        owner = users[0]
        wp = Workplan.objects.create(name="WP3", project=project, owner=owner, created_by=owner)
        ms = Milestone.objects.create(name="MS2", workplan=wp, status="pending", created_by=owner)
        perms = compute_milestone_permissions(ms, owner)
        assert perms["can_activate"] is True
        assert perms["can_complete"] is False

    def test_no_membership_all_false(self, project_with_members):
        """DoD #14"""
        from core.permissions_computer import compute_project_permissions
        project, users = project_with_members
        outsider = users[3]
        perms = compute_project_permissions(project, outsider)
        assert perms["can_edit"] is False
        assert perms["can_delete"] is False
        assert perms["can_archive"] is False
        assert perms["can_manage_members"] is False
