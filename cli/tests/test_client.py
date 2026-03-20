import pytest
import requests_mock as rm_module
from vtf.client import VTFClient, VTFAPIError


BASE_URL = "http://localhost:8000"
TOKEN = "testtoken123"


@pytest.fixture
def client():
    return VTFClient(BASE_URL, TOKEN)


@pytest.fixture
def client_no_token():
    return VTFClient(BASE_URL)


def test_get_request(client, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/health", json={"status": "ok"})
    result = client.get("/v1/health")
    assert result == {"status": "ok"}


def test_post_request(client, requests_mock):
    requests_mock.post(f"{BASE_URL}/v1/tasks", json={"id": 1, "title": "Test"})
    result = client.post("/v1/tasks", data={"title": "Test"})
    assert result["id"] == 1


def test_patch_request(client, requests_mock):
    requests_mock.patch(f"{BASE_URL}/v1/tasks/1", json={"id": 1, "title": "Updated"})
    result = client.patch("/v1/tasks/1", data={"title": "Updated"})
    assert result["title"] == "Updated"


def test_delete_request_no_content(client, requests_mock):
    requests_mock.delete(f"{BASE_URL}/v1/tasks/1", status_code=204, content=b"")
    result = client.delete("/v1/tasks/1")
    assert result == {}


def test_auth_header_sent(client, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/health", json={"status": "ok"})
    client.get("/v1/health")
    assert requests_mock.last_request.headers["Authorization"] == f"Token {TOKEN}"


def test_no_auth_header_when_no_token(client_no_token, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/health", json={"status": "ok"})
    client_no_token.get("/v1/health")
    assert "Authorization" not in requests_mock.last_request.headers


def test_content_type_header(client, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/health", json={"status": "ok"})
    client.get("/v1/health")
    assert requests_mock.last_request.headers["Content-Type"] == "application/json"


def test_raises_vtf_api_error_on_4xx(client, requests_mock):
    requests_mock.get(
        f"{BASE_URL}/v1/tasks/999",
        status_code=404,
        json={"error": {"message": "Not found"}},
    )
    with pytest.raises(VTFAPIError) as exc_info:
        client.get("/v1/tasks/999")
    assert exc_info.value.status_code == 404
    assert "Not found" in str(exc_info.value)


def test_raises_vtf_api_error_on_5xx(client, requests_mock):
    requests_mock.get(
        f"{BASE_URL}/v1/tasks",
        status_code=500,
        json={"error": {"message": "Internal server error"}},
    )
    with pytest.raises(VTFAPIError) as exc_info:
        client.get("/v1/tasks")
    assert exc_info.value.status_code == 500


def test_raises_vtf_api_error_on_401(client, requests_mock):
    requests_mock.get(
        f"{BASE_URL}/v1/tasks",
        status_code=401,
        json={"detail": "Authentication credentials were not provided."},
    )
    with pytest.raises(VTFAPIError) as exc_info:
        client.get("/v1/tasks")
    assert exc_info.value.status_code == 401


def test_health_method(client, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/health", json={"status": "ok"})
    result = client.health()
    assert result == {"status": "ok"}


def test_trailing_slash_stripped():
    c = VTFClient("http://localhost:8000/")
    assert c.api_url == "http://localhost:8000"


def test_get_with_params(client, requests_mock):
    requests_mock.get(f"{BASE_URL}/v1/tasks", json={"results": []})
    client.get("/v1/tasks", params={"status": "open"})
    assert requests_mock.last_request.qs["status"] == ["open"]
