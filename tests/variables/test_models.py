"""Model tests for the variables substrate (C.2 Slice 1).

Direct ORM construction (not shared factories) so these tests stay self-contained
while the models are being built test-first.
"""
import uuid

import pytest
from django.db import IntegrityError
from django.utils import timezone

from tests.factories import ProjectFactory, TaskFactory
from variables.models import ProjectVariable, VariableAudit


@pytest.mark.django_db
class TestProjectVariable:
    def test_create_minimal(self):
        p = ProjectFactory()
        v = ProjectVariable.objects.create(project=p, name="GH_TOKEN", role="executor")
        assert v.id and len(v.id) == 21  # NanoID surrogate PK
        assert v.name == "GH_TOKEN"
        assert v.role == "executor"

    def test_defaults(self):
        v = ProjectVariable.objects.create(project=ProjectFactory(), name="X", role="executor")
        assert v.scope == "project"
        assert v.required is True
        assert v.description in (None, "")

    def test_unique_together_violation(self):
        p = ProjectFactory()
        ProjectVariable.objects.create(project=p, name="GH_TOKEN", role="executor")
        with pytest.raises(IntegrityError):
            ProjectVariable.objects.create(project=p, name="GH_TOKEN", role="executor")

    def test_same_name_different_role_allowed(self):
        p = ProjectFactory()
        ProjectVariable.objects.create(project=p, name="GH_TOKEN", role="executor")
        v2 = ProjectVariable.objects.create(project=p, name="GH_TOKEN", role="judge")
        assert v2.pk

    def test_same_name_different_project_allowed(self):
        ProjectVariable.objects.create(project=ProjectFactory(), name="GH_TOKEN", role="executor")
        v2 = ProjectVariable.objects.create(project=ProjectFactory(), name="GH_TOKEN", role="executor")
        assert v2.pk

    def test_get_project_id(self):
        p = ProjectFactory()
        v = ProjectVariable.objects.create(project=p, name="X", role="executor")
        assert v.get_project_id() == p.id


@pytest.mark.django_db
class TestVariableAudit:
    def _make(self, **kw):
        defaults = dict(
            variable_name="GH_TOKEN",
            variable_scope="project",
            vault_path="secret/apps/vtaskforge/dev/projects/abad/executor/GH_TOKEN",
            result="success",
            duration_ms=12,
            controller_id="controller-0",
            timestamp=timezone.now(),
        )
        defaults.update(kw)
        defaults.setdefault("project", ProjectFactory())
        return VariableAudit.objects.create(**defaults)

    def test_create_each_result(self):
        for result in ["success", "not_found", "empty", "unreachable", "permission_denied"]:
            a = self._make(result=result)
            assert a.result == result

    def test_uuid_primary_key(self):
        a = self._make()
        assert isinstance(a.audit_id, uuid.UUID)

    def test_never_stores_value(self):
        """Audit must never carry the value, a hash, or a prefix (design §Audit-log integrity)."""
        names = {f.name for f in VariableAudit._meta.get_fields()}
        for forbidden in ("value", "value_hash", "value_prefix", "secret", "secret_value", "data"):
            assert forbidden not in names

    def test_task_and_project_nullable(self):
        a = self._make(task=None)
        assert a.task_id is None
