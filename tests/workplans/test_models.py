import pytest
from django.utils import timezone

from workplans.models import Workplan


@pytest.mark.django_db
class TestWorkplanModel:
    def test_create_workplan_minimal(self):
        wp = Workplan.objects.create(name="Test Workplan")
        assert wp.id is not None
        assert len(wp.id) == 21
        assert wp.name == "Test Workplan"
        assert wp.status == "active"
        assert wp.description == ""
        assert wp.owner == ""
        assert wp.tags == []
        assert wp.target_date is None
        assert wp.default_needs_review_before_start is False
        assert wp.default_needs_review_on_completion is False
        assert wp.created_by == ""

    def test_create_workplan_all_fields(self):
        target = timezone.now()
        wp = Workplan.objects.create(
            name="Full Workplan",
            description="A description",
            status="completed",
            owner="alice",
            tags=["backend", "api"],
            target_date=target,
            default_needs_review_before_start=True,
            default_needs_review_on_completion=True,
            created_by="bob",
        )
        assert wp.name == "Full Workplan"
        assert wp.description == "A description"
        assert wp.status == "completed"
        assert wp.owner == "alice"
        assert wp.tags == ["backend", "api"]
        assert wp.target_date == target
        assert wp.default_needs_review_before_start is True
        assert wp.default_needs_review_on_completion is True
        assert wp.created_by == "bob"

    def test_timestamps_auto_populated(self):
        wp = Workplan.objects.create(name="Timestamps Test")
        assert wp.created_at is not None
        assert wp.updated_at is not None

    def test_str_representation(self):
        wp = Workplan.objects.create(name="My Workplan")
        assert str(wp) == "My Workplan"

    def test_nanoid_primary_key(self):
        wp1 = Workplan.objects.create(name="WP1")
        wp2 = Workplan.objects.create(name="WP2")
        assert wp1.id != wp2.id
        assert len(wp1.id) == 21

    def test_status_choices(self):
        choices = dict(Workplan.STATUS_CHOICES)
        assert "active" in choices
        assert "completed" in choices
        assert "archived" in choices

    def test_default_ordering(self):
        wp1 = Workplan.objects.create(name="First")
        wp2 = Workplan.objects.create(name="Second")
        workplans = list(Workplan.objects.all())
        # Most recently created should come first
        assert workplans[0].id == wp2.id
        assert workplans[1].id == wp1.id

    def test_tags_accepts_list(self):
        wp = Workplan.objects.create(name="Tagged", tags=["tag1", "tag2", "tag3"])
        wp.refresh_from_db()
        assert wp.tags == ["tag1", "tag2", "tag3"]
