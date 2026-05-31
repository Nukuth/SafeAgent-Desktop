from typing import Any

from safeagent.server.db import TaskStore
from safeagent.server.settings import ServerSettings
from safeagent.shared.auth import require_bearer_token
from safeagent.shared.enums import EventType, NetworkMode, RemotePermission, RiskLevel, Severity, TaskStatus
from safeagent.shared.errors import ErrorEnvelope, SafeAgentError
from safeagent.shared.redaction import redact_payload
from safeagent.shared.remote_permissions import (
    require_approval_permission,
    require_submit_task_permission,
    validate_task_remote_permission,
)
from safeagent.shared.schemas import ApprovalRecord, RunEvent, TaskCreate


def create_app():  # type: ignore[no-untyped-def]
    try:
        from fastapi import Depends, FastAPI, Header, HTTPException
        from fastapi.exceptions import RequestValidationError
        from fastapi.responses import JSONResponse
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover - exercised only without dependencies
        raise RuntimeError("Install project dependencies before starting the FastAPI server") from exc

    settings = ServerSettings.from_env()
    store = TaskStore(settings.db_path)
    app = FastAPI(title="SafeAgent Control Plane", version="0.1.0")

    class TaskCreateBody(BaseModel):
        content: str = Field(min_length=1, max_length=8000)
        device_id: str = Field(min_length=1, max_length=128)
        requested_profile: str | None = Field(default=None, max_length=128)
        remote_permission: str = "submit_task"

    class EventBody(BaseModel):
        run_id: str
        agent: str
        event_type: str
        summary: str
        risk_level: str = "low"
        network_mode: str = "api_only"
        details: dict[str, Any] = Field(default_factory=dict)

    class ApprovalBody(BaseModel):
        run_id: str
        decision: str
        approved_by: str
        approval_scope: str = "plan_only"
        plan_hash: str | None = None
        expires_at: str | None = None

    class StatusBody(BaseModel):
        status: str

    def require_auth(authorization: str | None = Header(default=None)) -> None:
        require_bearer_token(authorization, settings.token)

    def require_worker_auth(authorization: str | None = Header(default=None)) -> None:
        require_bearer_token(authorization, settings.worker_token)

    @app.exception_handler(SafeAgentError)
    async def safeagent_error_handler(_request, exc: SafeAgentError):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=400, content={"error": redact_payload(exc.envelope.to_dict())})

    @app.exception_handler(HTTPException)
    async def http_error_handler(_request, exc: HTTPException):  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": _api_validation_error(
                    message="API request failed validation",
                    details={"http_status": exc.status_code, "detail": exc.detail},
                )
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_request, exc: RequestValidationError):  # type: ignore[no-untyped-def]
        return JSONResponse(
            status_code=422,
            content={
                "error": _api_validation_error(
                    message="API request body or parameters failed validation",
                    details={"errors": exc.errors()},
                )
            },
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/tasks", dependencies=[Depends(require_auth)])
    def create_task(
        body: TaskCreateBody,
        x_safeagent_remote_permission: str = Header(default=RemotePermission.SUBMIT_TASK.value),
    ) -> dict[str, Any]:
        require_submit_task_permission(x_safeagent_remote_permission)
        task = TaskCreate(
            content=body.content,
            device_id=body.device_id,
            requested_profile=body.requested_profile,
            remote_permission=validate_task_remote_permission(body.remote_permission),
        )
        return {"task": store.create_task(task).to_dict()}

    @app.get("/api/tasks/pending", dependencies=[Depends(require_worker_auth)])
    def pending(device_id: str, limit: int = 5) -> dict[str, Any]:
        return {"tasks": store.claim_pending(device_id, limit=max(1, min(limit, 20)))}

    @app.post("/api/tasks/{task_id}/heartbeat", dependencies=[Depends(require_worker_auth)])
    def heartbeat(task_id: str, body: dict[str, Any]) -> dict[str, str]:
        device_id = str(body.get("device_id", "unknown"))
        store.heartbeat(device_id, redact_payload({"task_id": task_id, **body}))
        return {"status": "ok"}

    @app.get("/api/devices/{device_id}/heartbeat", dependencies=[Depends(require_auth)])
    def latest_heartbeat(device_id: str) -> dict[str, Any]:
        return {"heartbeat": store.latest_heartbeat(device_id)}

    @app.post("/api/tasks/{task_id}/events", dependencies=[Depends(require_worker_auth)])
    def append_event(task_id: str, body: EventBody) -> dict[str, Any]:
        try:
            event = RunEvent(
                task_id=task_id,
                run_id=body.run_id,
                agent=body.agent,
                event_type=EventType(body.event_type),
                summary=body.summary,
                risk_level=RiskLevel(body.risk_level),
                network_mode=NetworkMode(body.network_mode),
                details=redact_payload(body.details),
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        store.append_event(event)
        return {"event_id": event.event_id}

    @app.post("/api/tasks/{task_id}/approval", dependencies=[Depends(require_auth)])
    def record_approval(
        task_id: str,
        body: ApprovalBody,
        x_safeagent_remote_permission: str = Header(default=RemotePermission.SUBMIT_TASK.value),
    ) -> dict[str, Any]:
        require_approval_permission(x_safeagent_remote_permission)
        if body.decision not in {"approved", "rejected"}:
            raise HTTPException(status_code=422, detail="decision must be approved or rejected")
        approval = ApprovalRecord(
            task_id=task_id,
            run_id=body.run_id,
            decision=body.decision,  # type: ignore[arg-type]
            approved_by=body.approved_by,
            approval_scope=body.approval_scope,  # type: ignore[arg-type]
            plan_hash=body.plan_hash,
            expires_at=body.expires_at,
        )
        store.record_approval(approval)
        store.update_task_status(
            task_id,
            TaskStatus.PENDING if body.decision == "approved" else TaskStatus.REJECTED,
        )
        return {"approval": redact_payload(approval.to_dict())}

    @app.get("/api/tasks/{task_id}/approval/latest", dependencies=[Depends(require_worker_auth)])
    def latest_approval(task_id: str) -> dict[str, Any]:
        approval = store.latest_approval_for_task(task_id)
        return {"approval": approval}

    @app.post("/api/tasks/{task_id}/status", dependencies=[Depends(require_worker_auth)])
    def update_status(task_id: str, body: StatusBody) -> dict[str, str]:
        try:
            status = TaskStatus(body.status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"invalid status: {body.status}") from exc
        store.update_task_status(task_id, status)
        return {"status": status.value}

    @app.get("/api/runs/{run_id}", dependencies=[Depends(require_auth)])
    def get_run(run_id: str) -> dict[str, Any]:
        return store.get_run(run_id)

    return app


def _api_validation_error(message: str, details: dict[str, Any]) -> dict[str, Any]:
    return redact_payload(
        ErrorEnvelope(
            code="validation.failed",
            module="server.app",
            message=message,
            severity=Severity.WARNING,
            retriable=False,
            details=details,
        ).to_dict()
    )
