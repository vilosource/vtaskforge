"""Project.slug — K8s-safe operational identity (C.2 Slice 2).

The slug is the Vault-path segment + future per-project SA suffix; it is
auto-derived from the name, validated as an RFC 1123 label (≤63), unique, and
immutable after creation. See docs/design/vtaskforge-variables-C2-PLAN.md §Q1.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework import status

from projects.models import Project
from tests.factories import ProjectFactory


@pytest.mark.django_db
class TestProjectSlugModel:
    def test_autoderived_from_name(self):
        p = Project.objects.create(name="Compass Group")
        assert p.slug == "compass-group"

    def test_autoderive_lowercases_and_strips_specials(self):
        p = Project.objects.create(name="  ABAD_Dashboard!!  ")
        assert p.slug == "abad-dashboard"

    def test_autoderive_dedupes_on_collision(self):
        a = Project.objects.create(name="Foo")
        b = Project.objects.create(name="Foo")
        assert a.slug == "foo"
        assert b.slug != a.slug and b.slug.startswith("foo")

    def test_explicit_slug_respected(self):
        p = Project.objects.create(name="Whatever", slug="abad")
        assert p.slug == "abad"

    def test_slug_is_unique(self):
        Project.objects.create(name="X", slug="dup")
        with pytest.raises(IntegrityError):
            Project.objects.create(name="Y", slug="dup")

    def test_slug_immutable_after_create(self):
        p = Project.objects.create(name="Stable")
        original = p.slug
        p.name = "Renamed Display"
        p.save()
        p.refresh_from_db()
        assert p.slug == original  # rename of display name never changes slug

    @pytest.mark.parametrize("bad", ["BadSlug", "bad_slug", "-bad", "bad-", "a" * 64, "bad slug"])
    def test_validator_rejects_invalid(self, bad):
        p = Project(name="X", slug=bad)
        with pytest.raises(ValidationError):
            p.full_clean()

    def test_blank_slug_autoderives_from_name(self):
        # blank="" is not a validator error (blank=True) — save() derives instead.
        p = Project.objects.create(name="Hello World", slug="")
        assert p.slug == "hello-world"


@pytest.mark.django_db
class TestProjectSlugAPI:
    def test_create_autoderives_slug(self, api_client):
        r = api_client.post("/v1/projects/", {"name": "Compass Group"}, format="json")
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["slug"] == "compass-group"

    def test_create_with_explicit_slug(self, api_client):
        r = api_client.post("/v1/projects/", {"name": "X", "slug": "abad"}, format="json")
        assert r.status_code == status.HTTP_201_CREATED
        assert r.data["slug"] == "abad"

    def test_create_invalid_slug_rejected(self, api_client):
        r = api_client.post("/v1/projects/", {"name": "X", "slug": "Bad_Slug"}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_slug_rejected(self, api_client):
        ProjectFactory(slug="taken")
        r = api_client.post("/v1/projects/", {"name": "Y", "slug": "taken"}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_slug_immutable_on_patch(self, api_client):
        p = ProjectFactory()
        r = api_client.patch(f"/v1/projects/{p.id}/", {"slug": "totally-new"}, format="json")
        assert r.status_code == status.HTTP_400_BAD_REQUEST

    def test_patch_same_slug_is_ok(self, api_client):
        p = ProjectFactory()
        r = api_client.patch(f"/v1/projects/{p.id}/", {"slug": p.slug, "name": "New Name"}, format="json")
        assert r.status_code == status.HTTP_200_OK

    def test_lookup_by_slug(self, api_client):
        p = ProjectFactory(name="Lookup Me")
        r = api_client.get(f"/v1/projects/{p.slug}/")
        assert r.status_code == status.HTTP_200_OK
        assert r.data["id"] == p.id
