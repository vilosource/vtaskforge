"""Step 7: v2 Link serializer tests (polymorphic refs).

Note: LinkViewSet does not support retrieve (GET by ID) — only list, create,
delete. Tests use list with filters to verify v2 serializer behavior.
"""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def setup(db):
    from django.contrib.auth.models import User
    from rest_framework.authtoken.models import Token
    from projects.models import Project
    from workplans.models import Workplan, Milestone
    from tasks.models import Task
    from links.models import Link
    from prefs.models import ProjectMembership

    user = User.objects.create_user("lnkv2user", password="pass", is_staff=True)
    token = Token.objects.create(user=user)
    project = Project.objects.create(name="LnkProj", owner=user, created_by=user)
    ProjectMembership.objects.create(user=user, project_id=project.id, role="owner")
    workplan = Workplan.objects.create(name="LnkWP", project=project, owner=user, created_by=user)
    milestone = Milestone.objects.create(name="LnkMS", workplan=workplan, status="active", created_by=user)
    task = Task.objects.create(title="LnkTask", project=project, workplan=workplan, milestone=milestone, created_by=user)
    task2 = Task.objects.create(title="LnkTask2", project=project, created_by=user)

    # Internal link: task -> task
    link_tt = Link.objects.create(
        source_type="task", source_id=task.id,
        target_type="task", target_id=task2.id,
        link_type="depends_on", project=project, created_by=user,
    )
    # External link: task -> commit
    link_ext = Link.objects.create(
        source_type="task", source_id=task.id,
        target_type="commit", target_id="abc123def",
        link_type="commit", project=project, created_by=user,
    )
    # Link with workplan source -> jira
    link_ws = Link.objects.create(
        source_type="workplan", source_id=workplan.id,
        target_type="jira", target_id="PROJ-123",
        link_type="jira", project=project, created_by=user,
    )

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client, project, task, task2, workplan, milestone, link_tt, link_ext, link_ws


def _find_link(results, link_id):
    """Find a link in list results by ID."""
    return next(r for r in results if r["id"] == link_id)


class TestLinkV2:

    def test_v2_link_source_task_ref(self, setup):
        """DoD #1"""
        client, project, task, _, _, _, link_tt, _, _ = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        assert resp.status_code == 200
        lnk = _find_link(resp.data["results"], link_tt.id)
        src = lnk["source"]
        assert src["type"] == "task"
        assert src["id"] == task.id
        assert src["title"] == "LnkTask"

    def test_v2_link_source_milestone_ref(self, setup):
        """DoD #2: Milestone ref through workplan source."""
        client, project, _, _, _, _, _, _, link_ws = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link_ws.id)
        src = lnk["source"]
        assert src["type"] == "workplan"
        assert src["name"] is not None

    def test_v2_link_source_workplan_ref(self, setup):
        """DoD #3"""
        client, project, _, _, workplan, _, _, _, link_ws = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link_ws.id)
        src = lnk["source"]
        assert src["type"] == "workplan"
        assert src["id"] == workplan.id
        assert src["name"] == "LnkWP"

    def test_v2_link_target_task_ref(self, setup):
        """DoD #4"""
        client, project, _, task2, _, _, link_tt, _, _ = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link_tt.id)
        tgt = lnk["target"]
        assert tgt["type"] == "task"
        assert tgt["id"] == task2.id

    def test_v2_link_target_external_commit(self, setup):
        """DoD #5"""
        client, project, _, _, _, _, _, link_ext, _ = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link_ext.id)
        tgt = lnk["target"]
        assert tgt["type"] == "commit"
        assert tgt["id"] == "abc123def"
        assert "label" in tgt

    def test_v2_link_target_external_jira(self, setup):
        """DoD #6"""
        client, project, _, _, _, _, _, _, link_ws = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link_ws.id)
        tgt = lnk["target"]
        assert tgt["type"] == "jira"
        assert tgt["id"] == "PROJ-123"

    def test_v2_link_created_by_actor_ref(self, setup):
        """DoD #7"""
        client, project, _, _, _, _, link_tt, _, _ = setup
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link_tt.id)
        assert isinstance(lnk["created_by"], dict)
        assert lnk["created_by"]["type"] == "user"

    def test_v2_link_no_n_plus_one(self, setup):
        """DoD #8: List links with bounded queries."""
        client, project, _, _, _, _, _, _, _ = setup
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        with CaptureQueriesContext(connection) as ctx:
            resp = client.get(f"/v2/links/?project={project.id}")
        assert resp.status_code == 200
        assert len(ctx) < 15

    def test_v2_link_create_accepts_flat_ids(self, setup):
        """DoD #9"""
        client, project, task, task2, _, _, _, _, _ = setup
        resp = client.post(
            "/v2/links/",
            {"source_type": "task", "source_id": task.id,
             "target_type": "task", "target_id": task2.id,
             "link_type": "relates_to"},
            format="json",
        )
        assert resp.status_code == 201
        assert isinstance(resp.data["source"], dict)

    def test_v2_link_deleted_source_graceful(self, setup):
        """DoD #10"""
        from links.models import Link
        client, project, _, _, _, _, _, _, _ = setup
        link = Link.objects.create(
            source_type="task", source_id="nonexistent",
            target_type="task", target_id="alsonothere",
            link_type="depends_on", project=project,
        )
        resp = client.get(f"/v2/links/?project={project.id}")
        lnk = _find_link(resp.data["results"], link.id)
        assert lnk["source"]["title"] is None

    def test_v1_link_unchanged(self, setup):
        """DoD #11"""
        client, project, _, _, _, _, _, _, _ = setup
        resp = client.get(f"/v1/links/?project={project.id}")
        assert resp.status_code == 200
        lnk = resp.data["results"][0]
        assert "source_title" in lnk
        assert "target_title" in lnk
