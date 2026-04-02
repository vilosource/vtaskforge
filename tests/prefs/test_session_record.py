"""TDD tests for SessionRecord model.

Phase 2 of User Management: lightweight session index.
"""

import pytest
from django.contrib.auth.models import User

from prefs.models import SessionRecord


@pytest.mark.django_db
class TestSessionRecord:
    def test_create_session_record(self):
        user = User.objects.create_user("human1", password="pass")
        record = SessionRecord.objects.create(
            user=user, project_id="proj1", role="architect", channel="web"
        )
        assert record.pk is not None
        assert record.project_id == "proj1"
        assert record.role == "architect"

    def test_ordering_most_recent_first(self):
        user = User.objects.create_user("human2", password="pass")
        r1 = SessionRecord.objects.create(
            user=user, project_id="p1", role="assistant"
        )
        r2 = SessionRecord.objects.create(
            user=user, project_id="p2", role="architect"
        )
        records = list(SessionRecord.objects.filter(user=user))
        assert records[0].pk == r2.pk
        assert records[1].pk == r1.pk

    def test_filter_by_user(self):
        u1 = User.objects.create_user("u1", password="pass")
        u2 = User.objects.create_user("u2", password="pass")
        SessionRecord.objects.create(user=u1, project_id="p1", role="architect")
        SessionRecord.objects.create(user=u2, project_id="p1", role="assistant")
        assert SessionRecord.objects.filter(user=u1).count() == 1

    def test_filter_by_project(self):
        user = User.objects.create_user("human3", password="pass")
        SessionRecord.objects.create(user=user, project_id="proj-a", role="architect")
        SessionRecord.objects.create(user=user, project_id="proj-b", role="assistant")
        assert SessionRecord.objects.filter(project_id="proj-a").count() == 1

    def test_optional_cxdb_context_id(self):
        user = User.objects.create_user("human4", password="pass")
        r1 = SessionRecord.objects.create(
            user=user, project_id="p1", role="architect", cxdb_context_id=42
        )
        r2 = SessionRecord.objects.create(
            user=user, project_id="p2", role="assistant"
        )
        assert r1.cxdb_context_id == 42
        assert r2.cxdb_context_id is None
