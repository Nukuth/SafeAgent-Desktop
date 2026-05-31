from __future__ import annotations

from typing import Any

from safeagent.shared.errors import TransientUpstreamError
from safeagent.shared.enums import TaskStatus
from safeagent.shared.schemas import RunEvent


class ControlPlaneClient:
    def __init__(self, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def fetch_pending(self, device_id: str) -> list[dict[str, Any]]:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    f"{self.base_url}/api/tasks/pending",
                    params={"device_id": device_id},
                    headers=self.headers,
                )
                response.raise_for_status()
                return list(response.json().get("tasks", []))
        except Exception as exc:  # pragma: no cover - network path needs deps/server
            raise TransientUpstreamError("local_worker.client", "Failed to fetch pending tasks") from exc

    async def post_event(self, event: RunEvent) -> None:
        try:
            import httpx

            payload = event.to_dict()
            task_id = event.task_id
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.base_url}/api/tasks/{task_id}/events",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
        except Exception as exc:  # pragma: no cover
            raise TransientUpstreamError("local_worker.client", "Failed to post event") from exc

    async def heartbeat(self, task_id: str, payload: dict[str, Any]) -> None:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.base_url}/api/tasks/{task_id}/heartbeat",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
        except Exception as exc:  # pragma: no cover
            raise TransientUpstreamError("local_worker.client", "Failed to post heartbeat") from exc

    async def fetch_latest_approval(self, task_id: str) -> dict[str, Any] | None:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    f"{self.base_url}/api/tasks/{task_id}/approval/latest",
                    headers=self.headers,
                )
                response.raise_for_status()
                approval = response.json().get("approval")
                return approval if isinstance(approval, dict) else None
        except Exception as exc:  # pragma: no cover
            raise TransientUpstreamError("local_worker.client", "Failed to fetch latest approval") from exc

    async def update_status(self, task_id: str, status: TaskStatus) -> None:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{self.base_url}/api/tasks/{task_id}/status",
                    json={"status": status.value},
                    headers=self.headers,
                )
                response.raise_for_status()
        except Exception as exc:  # pragma: no cover
            raise TransientUpstreamError("local_worker.client", "Failed to update task status") from exc
