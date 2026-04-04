"""Step 8: v2 Task serializer tests — most complex entity."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from workplans.models import Workplan, Milestone
    from tasks.models import Task
    from agents.models import Agent
    from prefs.models import ProjectMembership

    user = User.objects.create_user("taskv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    agent_user = User.objects.create_user("agent-tv2", password="pass")
    agent = Agent.objects.create(id="agent-tv2", name="tv2-executor", user=agent_user, pod_name="pod-tv2")

    project = Project.objects.create(name="TV2Proj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    ProjectMembership.objects.create(user=agent_user, project_id=project.id, role="member")
    workplan = Workplan.objects.create(name="TV2WP", project=project, owner=user, created_by=user)
    milestone = Milestone.objects.create(name="TV2MS", workplan=workplan, status="active", created_by=user)

    # Draft task (not claimed)
    task_draft = Task.objects.create(
        title="DraftTask", project=project, workplan=workplan,
        milestone=milestone, created_by=user, status="draft",
    )
    # Doing task (claimed by agent)
    task_doing = Task.objects.create(
        title="DoingTask", project=project, workplan=workplan,
        milestone=milestone, created_by=user, status="doing",
        claimed_by=agent_user, assigned_to=agent_user,
    )
    # Done task
    task_done = Task.objects.create(
        title="DoneTask", project=project, created_by=user, status="done",
    )
    # Task with requires (JSONField — list of task IDs)
    task_draft.requires = [task_done.id]
    task_draft.save(update_fields=["requires"])

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, user, project, workplan, milestone, task_draft, task_doing, task_done, agent


class TestTaskV2:

    def test_v2_task_project_is_ref(self, setup):
        """DoD #1"""
        client, _, project, _, _, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        assert resp.status_code == 200
        proj = resp.data["project"]
        assert isinstance(proj, dict)
        assert proj["id"] == project.id
        assert proj["name"] == "TV2Proj"

    def test_v2_task_workplan_is_ref(self, setup):
        """DoD #2"""
        client, _, _, workplan, _, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        wp = resp.data["workplan"]
        assert isinstance(wp, dict)
        assert wp["id"] == workplan.id

    def test_v2_task_milestone_is_ref(self, setup):
        """DoD #3"""
        client, _, _, _, milestone, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        ms = resp.data["milestone"]
        assert isinstance(ms, dict)
        assert ms["id"] == milestone.id
        assert ms["status"] == "active"

    def test_v2_task_requires_are_task_refs(self, setup):
        """DoD #4"""
        client, _, _, _, _, task, _, task_done, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        reqs = resp.data["requires"]
        assert len(reqs) == 1
        assert isinstance(reqs[0], dict)
        assert reqs[0]["id"] == task_done.id
        assert reqs[0]["title"] == "DoneTask"

    def test_v2_task_claimed_by_actor_ref(self, setup):
        """DoD #5"""
        client, _, _, _, _, _, task_doing, _, agent = setup
        resp = client.get(f"/v2/tasks/{task_doing.id}/")
        cb = resp.data["claimed_by"]
        assert isinstance(cb, dict)
        assert cb["type"] == "agent"
        assert cb["name"] == "tv2-executor"
        assert cb["pod_name"] == "pod-tv2"

    def test_v2_task_assigned_to_actor_ref(self, setup):
        """DoD #6"""
        client, _, _, _, _, _, task_doing, _, _ = setup
        resp = client.get(f"/v2/tasks/{task_doing.id}/")
        at = resp.data["assigned_to"]
        assert isinstance(at, dict)
        assert at["type"] == "agent"

    def test_v2_task_created_by_actor_ref(self, setup):
        """DoD #7"""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        cb = resp.data["created_by"]
        assert isinstance(cb, dict)
        assert cb["type"] == "user"
        assert cb["username"] == "taskv2user"

    def test_v2_task_null_refs(self, setup):
        """DoD #8"""
        client, _, _, _, _, _, _, task_done, _ = setup
        resp = client.get(f"/v2/tasks/{task_done.id}/")
        assert resp.data["claimed_by"] is None
        assert resp.data["workplan"] is None
        assert resp.data["milestone"] is None

    def test_v2_task_has_permissions(self, setup):
        """DoD #9"""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        perms = resp.data["permissions"]
        assert "can_edit" in perms
        assert "can_delete" in perms
        assert "available_actions" in perms

    def test_v2_task_available_actions_draft(self, setup):
        """DoD #10"""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        actions = resp.data["permissions"]["available_actions"]
        assert "todo" in actions

    def test_v2_task_available_actions_done(self, setup):
        """DoD #11"""
        client, _, _, _, _, _, _, task_done, _ = setup
        resp = client.get(f"/v2/tasks/{task_done.id}/")
        assert resp.data["permissions"]["available_actions"] == []

    def test_v2_task_no_claimed_by_pod_name(self, setup):
        """DoD #12"""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.get(f"/v2/tasks/{task.id}/")
        assert "claimed_by_pod_name" not in resp.data

    def test_v2_task_create_accepts_bare_ids(self, setup):
        """DoD #13"""
        client, _, project, workplan, milestone, _, _, _, _ = setup
        resp = client.post("/v2/tasks/", {
            "title": "NewTask",
            "project": project.id,
            "workplan": workplan.id,
            "milestone": milestone.id,
        }, format="json")
        assert resp.status_code == 201
        assert isinstance(resp.data["project"], dict)

    def test_v2_task_patch_accepts_bare_ids(self, setup):
        """DoD #14"""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.patch(f"/v2/tasks/{task.id}/", {
            "title": "UpdatedTask",
        }, format="json")
        assert resp.status_code == 200
        assert isinstance(resp.data["project"], dict)
        assert resp.data["title"] == "UpdatedTask"

    def test_v2_task_expand_links_v2(self, setup):
        """DoD #15"""
        from links.models import Link
        client, user, project, _, _, task, _, task_done, _ = setup
        Link.objects.create(
            source_type="task", source_id=task.id,
            target_type="task", target_id=task_done.id,
            link_type="depends_on", project=project, created_by=user,
        )
        resp = client.get(f"/v2/tasks/{task.id}/?expand=links")
        assert resp.status_code == 200
        assert resp.data["links"] is not None
        assert len(resp.data["links"]) > 0
        assert "source" in resp.data["links"][0]  # v2 Link shape

    def test_v2_task_expand_reviews_v2(self, setup):
        """DoD #16"""
        from reviews.models import Review
        client, user, _, _, _, _, task_doing, _, _ = setup
        task_doing.status = "pending_completion_review"
        task_doing.save(update_fields=["status"])
        Review.objects.create(task=task_doing, decision="approved", reason="OK", reviewer=user, reviewer_type="human")
        resp = client.get(f"/v2/tasks/{task_doing.id}/?expand=reviews")
        assert resp.data["reviews"] is not None
        assert isinstance(resp.data["reviews"][0]["reviewer"], dict)

    def test_v2_task_expand_events_v2(self, setup):
        """DoD #17"""
        from events.models import TaskEvent
        client, user, _, _, _, task, _, _, _ = setup
        TaskEvent.objects.create(task=task, event_type="status_changed", trigger_source="test", actor=user)
        resp = client.get(f"/v2/tasks/{task.id}/?expand=events")
        assert resp.data["events"] is not None
        assert isinstance(resp.data["events"][0]["task"], dict)

    def test_v2_task_actions_return_v2(self, setup):
        """DoD #18: submit action returns v2 shape."""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.post(f"/v2/tasks/{task.id}/submit/")
        assert resp.status_code == 200
        assert isinstance(resp.data["project"], dict)

    def test_v2_task_claim_returns_v2(self, setup):
        """DoD #19: claim action returns v2 shape with ActorRef claimed_by."""
        from tasks.models import Task
        client, user, project, workplan, milestone, _, _, _, agent = setup
        # Create a fresh todo task for claiming
        task = Task.objects.create(
            title="ClaimMe", project=project, workplan=workplan,
            milestone=milestone, created_by=user, status="todo",
        )
        resp = client.post(f"/v2/tasks/{task.id}/claim/", {"agent_id": agent.id}, format="json")
        assert resp.status_code == 200
        assert isinstance(resp.data["claimed_by"], dict)
        assert resp.data["claimed_by"]["type"] == "agent"

    def test_v1_task_unchanged(self, setup):
        """DoD #20"""
        client, _, _, _, _, task, _, _, _ = setup
        resp = client.get(f"/v1/tasks/{task.id}/")
        assert resp.status_code == 200
        # v1: claimed_by is a string or null, project is bare ID
        assert isinstance(resp.data["project"], str)
        assert "permissions" not in resp.data
        assert "claimed_by_pod_name" in resp.data

    def test_v2_milestone_tasks_view(self, setup):
        """DoD #21"""
        client, _, _, _, milestone, _, _, _, _ = setup
        resp = client.get(f"/v2/milestones/{milestone.id}/tasks/")
        assert resp.status_code == 200
        results = resp.data["results"]
        if results:
            assert isinstance(results[0]["project"], dict)

    def test_v2_project_tasks_view(self, setup):
        """DoD #22"""
        client, user, project, _, _, _, _, _, _ = setup
        # Create a backlog task
        from tasks.models import Task
        Task.objects.create(title="BacklogTask", project=project, created_by=user)
        resp = client.get(f"/v2/projects/{project.id}/backlog/")
        assert resp.status_code == 200
        results = resp.data["results"]
        if results:
            assert isinstance(results[0]["project"], dict)
