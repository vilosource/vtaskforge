import pytest
from rest_framework import status
from rest_framework.test import APIClient

from links.models import Link


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def link(db):
    return Link.objects.create(
        source_type="task",
        source_id="taskid123456789012345",
        target_type="commit",
        target_id="sha123abc",
        link_type="commit",
        created_by="alice",
    )


@pytest.fixture
def link_payload():
    return {
        "source_type": "task",
        "source_id": "taskid123456789012345",
        "target_type": "commit",
        "target_id": "sha456def",
        "link_type": "commit",
    }


@pytest.mark.django_db
class TestLinkList:
    def test_list_returns_200(self, api_client):
        response = api_client.get("/v1/links/")
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_empty_when_no_links(self, api_client):
        response = api_client.get("/v1/links/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_list_returns_links(self, api_client, link):
        response = api_client.get("/v1/links/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == link.id

    def test_list_filter_by_source_id(self, api_client, db):
        link1 = Link.objects.create(
            source_type="task", source_id="source_aaa", target_type="commit",
            target_id="sha1", link_type="commit",
        )
        Link.objects.create(
            source_type="task", source_id="source_bbb", target_type="commit",
            target_id="sha2", link_type="commit",
        )
        response = api_client.get("/v1/links/?source_id=source_aaa")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == link1.id

    def test_list_filter_by_target_id(self, api_client, db):
        link1 = Link.objects.create(
            source_type="task", source_id="source_aaa", target_type="jira",
            target_id="PROJ-1", link_type="jira",
        )
        Link.objects.create(
            source_type="task", source_id="source_bbb", target_type="jira",
            target_id="PROJ-2", link_type="jira",
        )
        response = api_client.get("/v1/links/?target_id=PROJ-1")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == link1.id

    def test_list_filter_by_source_type(self, api_client, db):
        Link.objects.create(
            source_type="task", source_id="source_aaa", target_type="commit",
            target_id="sha1", link_type="commit",
        )
        Link.objects.create(
            source_type="workplan", source_id="source_bbb", target_type="commit",
            target_id="sha2", link_type="commit",
        )
        response = api_client.get("/v1/links/?source_type=workplan")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["source_type"] == "workplan"

    def test_list_filter_by_link_type(self, api_client, db):
        Link.objects.create(
            source_type="task", source_id="source_aaa", target_type="commit",
            target_id="sha1", link_type="commit",
        )
        Link.objects.create(
            source_type="task", source_id="source_bbb", target_type="jira",
            target_id="PROJ-1", link_type="jira",
        )
        response = api_client.get("/v1/links/?link_type=jira")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["link_type"] == "jira"

    def test_list_multiple_filters_combined(self, api_client, db):
        link1 = Link.objects.create(
            source_type="task", source_id="source_aaa", target_type="commit",
            target_id="sha1", link_type="commit",
        )
        Link.objects.create(
            source_type="task", source_id="source_bbb", target_type="commit",
            target_id="sha2", link_type="commit",
        )
        response = api_client.get("/v1/links/?source_id=source_aaa&link_type=commit")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["id"] == link1.id


@pytest.mark.django_db
class TestLinkCreate:
    def test_create_returns_201(self, api_client, link_payload):
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_returns_id(self, api_client, link_payload):
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert "id" in response.data
        assert len(response.data["id"]) == 21

    def test_create_with_metadata(self, api_client, link_payload):
        link_payload["metadata"] = {"branch": "main", "sha": "abc123"}
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["metadata"] == {"branch": "main", "sha": "abc123"}

    def test_create_with_created_by(self, api_client, link_payload):
        link_payload["created_by"] = "bob"
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["created_by"] == "bob"

    def test_create_persists_to_db(self, api_client, link_payload):
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert Link.objects.filter(id=response.data["id"]).exists()

    def test_create_missing_required_fields_returns_400(self, api_client):
        response = api_client.post("/v1/links/", {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_invalid_source_type_returns_400(self, api_client, link_payload):
        link_payload["source_type"] = "invalid_type"
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_invalid_link_type_returns_400(self, api_client, link_payload):
        link_payload["link_type"] = "not_a_valid_link_type"
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_free_form_target_type(self, api_client, link_payload):
        # target_type is free-form, any string should be accepted
        link_payload["target_type"] = "custom_external_system"
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["target_type"] == "custom_external_system"

    def test_create_id_is_read_only(self, api_client, link_payload):
        link_payload["id"] = "custom-id-1234567890"
        response = api_client.post("/v1/links/", link_payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["id"] != "custom-id-1234567890"

    def test_create_returns_all_fields(self, api_client, link_payload):
        response = api_client.post("/v1/links/", link_payload, format="json")
        expected_fields = [
            "id", "source_type", "source_id", "target_type", "target_id",
            "link_type", "metadata", "created_by", "created_at", "updated_at",
        ]
        for field in expected_fields:
            assert field in response.data


@pytest.mark.django_db
class TestLinkDelete:
    def test_delete_returns_204(self, api_client, link):
        response = api_client.delete(f"/v1/links/{link.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_removes_from_db(self, api_client, link):
        api_client.delete(f"/v1/links/{link.id}/")
        assert not Link.objects.filter(id=link.id).exists()

    def test_delete_nonexistent_returns_404(self, api_client):
        response = api_client.delete("/v1/links/nonexistentid12345678/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestLinkImmutability:
    def test_retrieve_not_allowed(self, api_client, link):
        response = api_client.get(f"/v1/links/{link.id}/")
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_patch_not_allowed(self, api_client, link):
        response = api_client.patch(
            f"/v1/links/{link.id}/",
            {"created_by": "hacker"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_put_not_allowed(self, api_client, link):
        response = api_client.put(
            f"/v1/links/{link.id}/",
            {"source_type": "workplan"},
            format="json",
        )
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
