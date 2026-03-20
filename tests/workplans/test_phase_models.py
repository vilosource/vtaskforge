import pytest

from workplans.models import Phase, Workplan


@pytest.fixture
def workplan(db):
    return Workplan.objects.create(name="Test Workplan")


@pytest.mark.django_db
class TestPhaseModel:
    def test_create_phase_minimal(self, workplan):
        phase = Phase.objects.create(name="Phase 1", workplan=workplan)
        assert phase.id is not None
        assert len(phase.id) == 21
        assert phase.name == "Phase 1"
        assert phase.workplan == workplan
        assert phase.status == "pending"
        assert phase.description == ""
        assert phase.order == 0
        assert phase.default_needs_review_before_start is None
        assert phase.default_needs_review_on_completion is None
        assert phase.created_by == ""

    def test_create_phase_all_fields(self, workplan):
        phase = Phase.objects.create(
            name="Full Phase",
            description="A description",
            workplan=workplan,
            status="active",
            order=5,
            default_needs_review_before_start=True,
            default_needs_review_on_completion=False,
            created_by="alice",
        )
        assert phase.name == "Full Phase"
        assert phase.description == "A description"
        assert phase.status == "active"
        assert phase.order == 5
        assert phase.default_needs_review_before_start is True
        assert phase.default_needs_review_on_completion is False
        assert phase.created_by == "alice"

    def test_review_flags_default_to_null(self, workplan):
        phase = Phase.objects.create(name="Phase", workplan=workplan)
        phase.refresh_from_db()
        assert phase.default_needs_review_before_start is None
        assert phase.default_needs_review_on_completion is None

    def test_review_flag_null_stored_as_null(self, workplan):
        phase = Phase.objects.create(
            name="Phase",
            workplan=workplan,
            default_needs_review_before_start=None,
        )
        phase.refresh_from_db()
        assert phase.default_needs_review_before_start is None

    def test_timestamps_auto_populated(self, workplan):
        phase = Phase.objects.create(name="Phase", workplan=workplan)
        assert phase.created_at is not None
        assert phase.updated_at is not None

    def test_str_representation(self, workplan):
        phase = Phase.objects.create(name="My Phase", workplan=workplan)
        assert str(phase) == "My Phase"

    def test_nanoid_primary_key(self, workplan):
        p1 = Phase.objects.create(name="Phase 1", workplan=workplan)
        p2 = Phase.objects.create(name="Phase 2", workplan=workplan)
        assert p1.id != p2.id
        assert len(p1.id) == 21

    def test_status_choices(self):
        choices = dict(Phase.STATUS_CHOICES)
        assert "pending" in choices
        assert "active" in choices
        assert "completed" in choices

    def test_cascade_delete_workplan(self, workplan):
        phase = Phase.objects.create(name="Phase", workplan=workplan)
        phase_id = phase.id
        workplan.delete()
        assert not Phase.objects.filter(id=phase_id).exists()

    def test_workplan_related_name(self, workplan):
        Phase.objects.create(name="Phase A", workplan=workplan)
        Phase.objects.create(name="Phase B", workplan=workplan)
        assert workplan.phases.count() == 2

    def test_default_ordering(self, workplan):
        p1 = Phase.objects.create(name="Phase 1", workplan=workplan, order=2)
        p2 = Phase.objects.create(name="Phase 2", workplan=workplan, order=1)
        phases = list(Phase.objects.filter(workplan=workplan))
        # order=1 comes before order=2
        assert phases[0].id == p2.id
        assert phases[1].id == p1.id
