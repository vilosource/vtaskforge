"""AsyncVtfClient — async client for the vtaskforge v2 API."""
from __future__ import annotations

from typing import AsyncIterator

from .async_transport import AsyncTransport
from .entities import Agent, Link, Milestone, Note, Project, Review, Task, Workplan
from .managers import _parse_paged
from .pagination import PagedResult


class _AsyncBaseManager:
    def __init__(self, transport: AsyncTransport):
        self._transport = transport


class AsyncTaskManager(_AsyncBaseManager):

    async def get(self, id: str, expand: list[str] | None = None) -> Task:
        params = {}
        if expand:
            params["expand"] = ",".join(expand)
        data = await self._transport.get(f"/v2/tasks/{id}/", params=params or None)
        return Task.model_validate(data)

    async def list(self, *, status: str | None = None, project_id: str | None = None,
                   page_size: int = 50) -> PagedResult[Task]:
        params: dict = {"page_size": page_size}
        if status:
            params["status"] = status
        if project_id:
            params["project"] = project_id
        data = await self._transport.get("/v2/tasks/", params=params)
        return _parse_paged(data, Task)

    async def list_all(self, **filters) -> AsyncIterator[Task]:
        params: dict = {k: v for k, v in filters.items() if v is not None}
        url = "/v2/tasks/"
        while url:
            data = await self._transport.get(url, params=params if url == "/v2/tasks/" else None)
            for item in data.get("results", []):
                yield Task.model_validate(item)
            url = data.get("next")

    async def create(self, *, title: str, project: str, **kwargs) -> Task:
        data = await self._transport.post("/v2/tasks/", json={"title": title, "project": project, **kwargs})
        return Task.model_validate(data)

    async def claim(self, id: str, *, agent_id: str) -> Task:
        data = await self._transport.post(f"/v2/tasks/{id}/claim/", json={"agent_id": agent_id})
        return Task.model_validate(data)

    async def submit(self, id: str) -> Task:
        data = await self._transport.post(f"/v2/tasks/{id}/submit/")
        return Task.model_validate(data)

    async def complete(self, id: str) -> Task:
        data = await self._transport.post(f"/v2/tasks/{id}/complete/")
        return Task.model_validate(data)


class AsyncProjectManager(_AsyncBaseManager):

    async def get(self, id: str) -> Project:
        data = await self._transport.get(f"/v2/projects/{id}/")
        return Project.model_validate(data)

    async def list(self, *, page_size: int = 50) -> PagedResult[Project]:
        data = await self._transport.get("/v2/projects/", params={"page_size": page_size})
        return _parse_paged(data, Project)


class AsyncVtfClient:
    """Asynchronous vtaskforge API client."""

    def __init__(
        self,
        url: str,
        token: str,
        timeout: float = 30.0,
        max_retries: int = 0,
        backoff_factor: float = 0.5,
    ):
        self._transport = AsyncTransport(
            base_url=url, token=token, timeout=timeout,
            max_retries=max_retries, backoff_factor=backoff_factor,
        )
        self.tasks = AsyncTaskManager(self._transport)
        self.projects = AsyncProjectManager(self._transport)

    async def close(self):
        await self._transport.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
