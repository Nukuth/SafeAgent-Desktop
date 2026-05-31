from __future__ import annotations

from typing import Any

from safeagent.shared.enums import Severity, TaskStatus
from safeagent.shared.errors import SafeAgentError, TransientUpstreamError, ValidationError
from safeagent.shared.redaction import redact_payload
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
                raise_for_control_plane_error(response, "fetch_pending")
                return list(response.json().get("tasks", []))
        except SafeAgentError:
            raise
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
                raise_for_control_plane_error(response, "post_event")
        except SafeAgentError:
            raise
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
                raise_for_control_plane_error(response, "heartbeat")
        except SafeAgentError:
            raise
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
                raise_for_control_plane_error(response, "fetch_latest_approval")
                approval = response.json().get("approval")
                return approval if isinstance(approval, dict) else None
        except SafeAgentError:
            raise
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
                raise_for_control_plane_error(response, "update_status")
        except SafeAgentError:
            raise
        except Exception as exc:  # pragma: no cover
            raise TransientUpstreamError("local_worker.client", "Failed to update task status") from exc


def raise_for_control_plane_error(response: Any, operation: str) -> None:
    try:
        response.raise_for_status()
    except Exception as exc:
        status_code = int(getattr(response, "status_code", 0) or 0)
        mapped = safeagent_error_from_response(response, operation)
        if mapped:
            raise mapped from exc
        if 400 <= status_code < 500:
            raise ValidationError(
                "local_worker.client",
                "Control plane rejected worker request",
                {
                    "operation": operation,
                    "http_status": status_code,
                    "response_text": redact_payload(getattr(response, "text", "")),
                },
            ) from exc
        raise TransientUpstreamError(
            "local_worker.client",
            "Control plane request failed",
            {"operation": operation, "http_status": status_code},
        ) from exc


def safeagent_error_from_response(response: Any, operation: str) -> SafeAgentError | None:
    try:
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    if not isinstance(error, dict):
        return None
    code = error.get("code")
    module = error.get("module")
    message = error.get("message")
    if not isinstance(code, str) or not isinstance(module, str) or not isinstance(message, str):
        return None
    severity = _parse_severity(error.get("severity"))
    details = error.get("details") if isinstance(error.get("details"), dict) else {}
    safe_details = redact_payload(
        {
            **details,
            "client_operation": operation,
            "http_status": int(getattr(response, "status_code", 0) or 0),
        }
    )
    return SafeAgentError(
        code,
        module,
        message,
        severity=severity,
        retriable=bool(error.get("retriable", False)),
        details=safe_details,
    )


def _parse_severity(value: object) -> Severity:
    try:
        return Severity(str(value))
    except ValueError:
        return Severity.ERROR
