"""
Synchronous REST API client for E2E test verification.

Used alongside the MCP client for dual-channel verification:
    MCP tool says "task claimed" + REST API confirms status=doing.
"""
import httpx


class RestTestClient:
    """Sync HTTP client for the vtf REST API.

    All requests include the Authorization header.  The base_url must
    include the /v1 prefix, e.g. http://localhost:18000/v1.
    """

    def __init__(self, base_url: str, token: str) -> None:
        self.client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Token {token}"},
            timeout=30.0,
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "RestTestClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def get_task(self, task_id: str) -> dict | None:
        """Return task data or None if not found."""
        r = self.client.get(f"/tasks/{task_id}/")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def list_tasks(self, **params) -> list[dict]:
        """Return the results list from GET /tasks/."""
        r = self.client.get("/tasks/", params=params)
        r.raise_for_status()
        return r.json()["results"]

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def get_project(self, project_id: str) -> dict | None:
        """Return project data or None if not found."""
        r = self.client.get(f"/projects/{project_id}/")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def list_projects(self, **params) -> list[dict]:
        """Return the results list from GET /projects/."""
        r = self.client.get("/projects/", params=params)
        r.raise_for_status()
        return r.json()["results"]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health(self) -> dict:
        """Return the /health response."""
        r = self.client.get("/health")
        r.raise_for_status()
        return r.json()
