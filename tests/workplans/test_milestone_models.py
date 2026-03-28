import pytest

from tests.factories import MilestoneFactory, WorkplanFactory
from workplans.models import Milestone, Workplan


@pytest.fixture
def workplan(db):
    return WorkplanFactory(name="Test Workplan")


@pytest.mark.django_db
class TestMilestoneModel:
    def test_create_milestone_minimal(self, workplan):
        milestone = Milestone.objects.create(name="Milestone 1", workplan=workplan)
        assert milestone.id is not None
        assert len(milestone.id) == 21
        assert milestone.name == "Milestone 1"
        assert milestone.workplan == workplan
        assert milestone.status == "pending"
        assert milestone.description == ""
        assert milestone.order == 0
        assert milestone.default_needs_review_before_start is None
        assert milestone.default_needs_review_on_completion is None
        assert milestone.created_by == ""

    def test_create_milestone_all_fields(self, workplan):
        milestone = MilestoneFactory(
            name="Full Milestone",
            description="A description",
            workplan=workplan,
            status="active",
            order=5,
            default_needs_review_before_start=True,
            default_needs_review_on_completion=False,
            created_by="alice",
        )
        assert milestone.name == "Full Milestone"
        assert milestone.description == "A description"
        assert milestone.status == "active"
        assert milestone.order == 5
        assert milestone.default_needs_review_before_start is True
        assert milestone.default_needs_review_on_completion is False
        assert milestone.created_by == "alice"

    def test_review_flags_default_to_null(self, workplan):
        milestone = MilestoneFactory(name="Milestone", workplan=workplan)
        milestone.refresh_from_db()
        assert milestone.default_needs_review_before_start is None
        assert milestone.default_needs_review_on_completion is None

    def test_review_flag_null_stored_as_null(self, workplan):
        milestone = MilestoneFactory(
            name="Milestone",
            workplan=workplan,
            default_needs_review_before_start=None,
        )
        milestone.refresh_from_db()
        assert milestone.default_needs_review_before_start is None

    def test_timestamps_auto_populated(self, workplan):
        milestone = MilestoneFactory(name="Milestone", workplan=workplan)
        assert milestone.created_at is not None
        assert milestone.updated_at is not None

    def test_str_representation(self, workplan):
        milestone = MilestoneFactory(name="My Milestone", workplan=workplan)
        assert str(milestone) == "My Milestone"

    def test_nanoid_primary_key(self, workplan):
        p1 = MilestoneFactory(name="Milestone 1", workplan=workplan)
        p2 = MilestoneFactory(name="Milestone 2", workplan=workplan)
        assert p1.id != p2.id
        assert len(p1.id) == 21

    def test_status_choices(self):
        choices = dict(Milestone.STATUS_CHOICES)
        assert "pending" in choices
        assert "active" in choices
        assert "completed" in choices

    def test_cascade_delete_workplan(self, workplan):
        milestone = MilestoneFactory(name="Milestone", workplan=workplan)
        milestone_id = milestone.id
        workplan.delete()
        assert not Milestone.objects.filter(id=milestone_id).exists()

    def test_workplan_related_name(self, workplan):
        MilestoneFactory(name="Milestone A", workplan=workplan)
        MilestoneFactory(name="Milestone B", workplan=workplan)
        assert workplan.milestones.count() == 2

    def test_default_ordering(self, workplan):
        p1 = MilestoneFactory(name="Milestone 1", workplan=workplan, order=2)
        p2 = MilestoneFactory(name="Milestone 2", workplan=workplan, order=1)
        milestones = list(Milestone.objects.filter(workplan=workplan))
        # order=1 comes before order=2
        assert milestones[0].id == p2.id
        assert milestones[1].id == p1.id
