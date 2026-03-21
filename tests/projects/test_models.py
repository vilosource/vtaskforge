import pytest

from projects.models import Project
from tests.factories import ProjectFactory


@pytest.mark.django_db
class TestProject:
    def test_create_project(self):
        project = ProjectFactory()
        assert project.id is not None
        assert len(project.id) == 21
        assert project.name.startswith("Project")
        assert project.status == "active"

    def test_project_defaults(self):
        project = Project.objects.create(name="Test Project")
        assert project.description == ""
        assert project.status == "active"
        assert project.repo_url == ""
        assert project.default_branch == "main"
        assert project.tags == []
        assert project.owner == ""
        assert project.created_by == ""

    def test_project_str_representation(self):
        project = ProjectFactory(name="My Project")
        assert str(project) == "My Project"

    def test_project_with_all_fields(self):
        project = Project.objects.create(
            name="Full Project",
            description="A complete project",
            status="archived",
            repo_url="https://github.com/example/repo.git",
            default_branch="develop",
            tags=["backend", "api"],
            owner="alice",
            created_by="bob",
        )
        assert project.name == "Full Project"
        assert project.description == "A complete project"
        assert project.status == "archived"
        assert project.repo_url == "https://github.com/example/repo.git"
        assert project.default_branch == "develop"
        assert project.tags == ["backend", "api"]
        assert project.owner == "alice"
        assert project.created_by == "bob"

    def test_project_ordering(self):
        # Projects should be ordered by -created_at (newest first)
        project1 = ProjectFactory(name="First")
        project2 = ProjectFactory(name="Second")
        projects = Project.objects.all()
        assert projects[0] == project2  # Newest first
        assert projects[1] == project1