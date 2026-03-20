import pytest

from links.models import Link, LINK_TYPE_CHOICES, SOURCE_TYPE_CHOICES


@pytest.mark.django_db
class TestLinkModel:
    def test_create_link_minimal(self):
        link = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="commit",
            target_id="abc123",
            link_type="commit",
        )
        assert link.id is not None
        assert len(link.id) == 21
        assert link.source_type == "task"
        assert link.source_id == "abc123def456ghi7890ab"
        assert link.target_type == "commit"
        assert link.target_id == "abc123"
        assert link.link_type == "commit"
        assert link.metadata is None
        assert link.created_by == ""

    def test_create_link_all_fields(self):
        link = Link.objects.create(
            source_type="workplan",
            source_id="abc123def456ghi7890ab",
            target_type="jira",
            target_id="PROJ-123",
            link_type="relates_to",
            metadata={"key": "value"},
            created_by="alice",
        )
        assert link.source_type == "workplan"
        assert link.target_type == "jira"
        assert link.target_id == "PROJ-123"
        assert link.link_type == "relates_to"
        assert link.metadata == {"key": "value"}
        assert link.created_by == "alice"

    def test_timestamps_auto_populated(self):
        link = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="commit",
            target_id="sha123",
            link_type="commit",
        )
        assert link.created_at is not None
        assert link.updated_at is not None

    def test_nanoid_primary_key(self):
        link1 = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="commit",
            target_id="sha1",
            link_type="commit",
        )
        link2 = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="commit",
            target_id="sha2",
            link_type="commit",
        )
        assert link1.id != link2.id
        assert len(link1.id) == 21

    def test_str_representation(self):
        link = Link.objects.create(
            source_type="task",
            source_id="taskid123456789012345",
            target_type="commit",
            target_id="sha123",
            link_type="commit",
        )
        assert "task" in str(link)
        assert "commit" in str(link)

    def test_link_type_choices(self):
        choices = dict(LINK_TYPE_CHOICES)
        assert "depends_on" in choices
        assert "blocks" in choices
        assert "relates_to" in choices
        assert "commit" in choices
        assert "mr" in choices
        assert "area" in choices
        assert "doc" in choices
        assert "file" in choices
        assert "jira" in choices

    def test_source_type_choices(self):
        choices = dict(SOURCE_TYPE_CHOICES)
        assert "workplan" in choices
        assert "phase" in choices
        assert "task" in choices

    def test_target_type_is_free_form(self):
        # target_type is not restricted to choices — any string is valid
        link = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="custom_external_system",
            target_id="ref-001",
            link_type="relates_to",
        )
        assert link.target_type == "custom_external_system"

    def test_metadata_accepts_dict(self):
        link = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="commit",
            target_id="sha123",
            link_type="commit",
            metadata={"branch": "main", "sha": "abc123"},
        )
        link.refresh_from_db()
        assert link.metadata == {"branch": "main", "sha": "abc123"}

    def test_metadata_accepts_none(self):
        link = Link.objects.create(
            source_type="task",
            source_id="abc123def456ghi7890ab",
            target_type="commit",
            target_id="sha123",
            link_type="commit",
            metadata=None,
        )
        assert link.metadata is None

    def test_db_indexes_exist(self):
        index_names = [idx.name for idx in Link._meta.indexes]
        # Verify two indexes are defined
        assert len(index_names) == 2
