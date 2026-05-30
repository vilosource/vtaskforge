"""Admission validation for a task's `variables:` spec (C.2 Slice 4).

Unit tests for `validate_task_variables` + integration tests for the
TaskSerializer admission gate on task submit.
"""
import pytest
from django.contrib.auth.models import User

from prefs.models import ProjectMembership
from tests.factories import ProjectFactory, ProjectVariableFactory
from variables.admission import levenshtein, near_matches, validate_task_variables


class TestLevenshtein:
    def test_distance(self):
        assert levenshtein("GH_TOKEN", "GH_TOKEN") == 0
        assert levenshtein("GH_TOKEN", "GH_TOKE") == 1
        assert levenshtein("abc", "xyz") == 3

    def test_near_matches_excludes_exact(self):
        assert near_matches("GH_TOKEN", ["GH_TOKE", "NPM_TOKEN"]) == ["GH_TOKE"]
        assert near_matches("GH_TOKEN", ["GH_TOKEN"]) == []


@pytest.mark.django_db
class TestValidateTaskVariables:
    def test_empty_is_valid(self):
        assert validate_task_variables(None, None) == []
        assert validate_task_variables([], None) == []

    def test_not_a_list(self):
        assert validate_task_variables({"name": "X"}, None)

    def test_missing_name(self):
        errs = validate_task_variables([{"source": {"kind": "literal", "value": "x"}}], None)
        assert any("name" in e for e in errs)

    def test_bad_source_kind(self):
        errs = validate_task_variables([{"name": "X", "source": {"kind": "bogus"}}], None)
        assert any("kind" in e for e in errs)

    def test_vault_path_forbidden(self):
        p = ProjectFactory()
        ProjectVariableFactory(project=p, name="GH_TOKEN", role="executor")
        errs = validate_task_variables(
            [{"name": "GH_TOKEN", "source": {"kind": "vault", "path": "secret/x"}}], p
        )
        assert any("path" in e for e in errs)

    def test_bad_vault_scope(self):
        errs = validate_task_variables(
            [{"name": "X", "source": {"kind": "vault", "scope": "global"}}], ProjectFactory()
        )
        assert any("scope" in e for e in errs)

    def test_literal_requires_value(self):
        errs = validate_task_variables([{"name": "X", "source": {"kind": "literal"}}], None)
        assert any("value" in e for e in errs)

    def test_required_set_coverage_missing(self):
        p = ProjectFactory()
        errs = validate_task_variables([{"name": "GH_TOKEN"}], p)
        assert any("not declared" in e for e in errs)

    def test_required_set_coverage_ok(self):
        p = ProjectFactory()
        ProjectVariableFactory(project=p, name="GH_TOKEN", role="executor")
        assert validate_task_variables([{"name": "GH_TOKEN"}], p) == []

    def test_binding_collision_env(self):
        p = ProjectFactory()
        ProjectVariableFactory(project=p, name="A", role="executor")
        ProjectVariableFactory(project=p, name="B", role="executor")
        errs = validate_task_variables(
            [{"name": "A", "target": {"env": "SHARED"}},
             {"name": "B", "target": {"env": "SHARED"}}], p
        )
        assert any("collide" in e for e in errs)

    def test_binding_collision_file(self):
        errs = validate_task_variables(
            [{"name": "A", "source": {"kind": "literal", "value": "1"}, "target": {"file": "/x"}},
             {"name": "B", "source": {"kind": "literal", "value": "2"}, "target": {"file": "/x"}}], None
        )
        assert any("collide" in e for e in errs)

    def test_shared_and_literal_skip_coverage(self):
        errs = validate_task_variables(
            [{"name": "LLM_KEY", "source": {"kind": "vault", "scope": "shared"}},
             {"name": "LOG", "source": {"kind": "literal", "value": "info"}}], ProjectFactory()
        )
        assert errs == []

    def test_default_env_binding_no_false_collision(self):
        p = ProjectFactory()
        ProjectVariableFactory(project=p, name="A", role="executor")
        ProjectVariableFactory(project=p, name="B", role="executor")
        # Distinct names → distinct default env bindings → no collision.
        assert validate_task_variables([{"name": "A"}, {"name": "B"}], p) == []


@pytest.fixture
def member_project(db, api_client):
    p = ProjectFactory()
    ProjectMembership.objects.create(
        user=User.objects.get(username="testuser"), project_id=p.id, role="owner"
    )
    return p


@pytest.mark.django_db
class TestTaskVariablesAdmissionAPI:
    def test_unknown_variable_rejected(self, api_client, member_project):
        r = api_client.post(
            "/v1/tasks/",
            {"title": "T", "project": member_project.id, "variables": [{"name": "UNDECLARED"}]},
            format="json",
        )
        assert r.status_code == 400
        assert "variables" in r.data

    def test_declared_variable_accepted(self, api_client, member_project):
        ProjectVariableFactory(project=member_project, name="GH_TOKEN", role="executor")
        r = api_client.post(
            "/v1/tasks/",
            {"title": "T", "project": member_project.id, "variables": [{"name": "GH_TOKEN"}]},
            format="json",
        )
        assert r.status_code == 201
        assert r.data["variables"] == [{"name": "GH_TOKEN"}]

    def test_task_without_variables_unaffected(self, api_client, member_project):
        r = api_client.post(
            "/v1/tasks/", {"title": "T", "project": member_project.id}, format="json"
        )
        assert r.status_code == 201
        assert r.data["variables"] == []

    def test_binding_collision_rejected(self, api_client, member_project):
        ProjectVariableFactory(project=member_project, name="A", role="executor")
        ProjectVariableFactory(project=member_project, name="B", role="executor")
        r = api_client.post(
            "/v1/tasks/",
            {
                "title": "T", "project": member_project.id,
                "variables": [
                    {"name": "A", "target": {"env": "X"}},
                    {"name": "B", "target": {"env": "X"}},
                ],
            },
            format="json",
        )
        assert r.status_code == 400
