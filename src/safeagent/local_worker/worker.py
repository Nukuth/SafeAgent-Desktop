from __future__ import annotations

import asyncio

from safeagent.local_worker.client import ControlPlaneClient
from safeagent.local_worker.orchestrator import LocalOrchestrator
from safeagent.local_worker.policy import PolicyEngine
from safeagent.local_worker.providers import build_provider_registry_from_config
from safeagent.local_worker.registry import load_default_registries
from safeagent.local_worker.settings import WorkerSettings
from safeagent.shared.audit_log import JsonlAuditLog
from safeagent.shared.enums import EventType, RiskLevel, Severity, TaskStatus
from safeagent.shared.errors import ErrorEnvelope, SafeAgentError
from safeagent.shared.ids import new_id
from safeagent.shared.redaction import redact_payload
from safeagent.shared.schemas import RunEvent
from safeagent.shared.time import utc_now_iso


class LocalWorker:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.audit = JsonlAuditLog(settings.logs_dir / "worker.jsonl")
        self.client = ControlPlaneClient(settings.control_url, settings.token)
        agent_registry, profile_registry = load_default_registries(settings.config_dir)
        provider_registry = build_provider_registry_from_config(settings.config_dir / "models.json")
        self.orchestrator = LocalOrchestrator(
            PolicyEngine(settings.workspace_root),
            agent_registry=agent_registry,
            profile_registry=profile_registry,
            provider_registry=provider_registry,
            emergency_local_model=settings.emergency_local_model,
            execution_mode=settings.execution_mode,
            execution_timeout_seconds=settings.execution_timeout_seconds,
            stdout_limit_chars=settings.stdout_limit_chars,
            stderr_limit_chars=settings.stderr_limit_chars,
            enable_live_readonly=settings.enable_live_readonly,
            graph_runtime=settings.graph_runtime,
        )

    async def run_once(self) -> int:
        await self._post_worker_heartbeat("poll_started")
        tasks = await self.client.fetch_pending(self.settings.device_id)
        for task in tasks:
            await self._handle_task_safely(task)
        await self._post_worker_heartbeat("poll_completed", task_count=len(tasks))
        return len(tasks)

    async def run_forever(self) -> None:
        while True:
            try:
                count = await self.run_once()
                self.audit.write(
                    {
                        "timestamp": utc_now_iso(),
                        "module": "local_worker",
                        "event": "poll_completed",
                        "task_count": count,
                    }
                )
            except SafeAgentError as exc:
                self.audit.write({"timestamp": utc_now_iso(), "error": exc.envelope.to_dict()})
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def _handle_task_safely(self, task: dict[str, object]) -> None:
        try:
            await self._handle_task(task)
        except SafeAgentError as exc:
            await self._record_task_failure(task, exc.envelope)
        except Exception as exc:  # pragma: no cover - defensive boundary for plugin/provider surprises
            await self._record_task_failure(
                task,
                ErrorEnvelope(
                    code="worker.task_failed",
                    module="local_worker.worker",
                    message="Task failed inside local worker isolation boundary",
                    severity=Severity.ERROR,
                    retriable=False,
                    details={
                        "exception_type": type(exc).__name__,
                        "exception_message": str(exc),
                    },
                ),
            )

    async def _handle_task(self, task: dict[str, object]) -> None:
        approval = await self.client.fetch_latest_approval(str(task["task_id"]))
        result = self.orchestrator.handle_task(task, approval=approval)
        self.audit.write(
            {
                "timestamp": utc_now_iso(),
                "module": "local_worker",
                "event": "task_handled",
                "task": redact_payload(task),
                "approval_present": approval is not None,
                "run_id": result.run_id,
                "status": result.status.value,
                "policy": result.policy.to_dict(),
            }
        )
        for event in result.events:
            self.audit.write(event.to_dict())
            await self.client.post_event(event)
        await self.client.update_status(str(task["task_id"]), result.status)

    async def _post_worker_heartbeat(self, phase: str, task_count: int | None = None) -> None:
        payload: dict[str, object] = {
            "device_id": self.settings.device_id,
            "phase": phase,
            "status": "online",
            "timestamp": utc_now_iso(),
            "poll_interval_seconds": self.settings.poll_interval_seconds,
        }
        if task_count is not None:
            payload["task_count"] = task_count
        try:
            await self.client.heartbeat("worker", payload)
        except SafeAgentError as exc:
            self.audit.write(
                {
                    "timestamp": utc_now_iso(),
                    "module": "local_worker",
                    "event": "heartbeat_failed",
                    "phase": phase,
                    "error": redact_payload(exc.envelope.to_dict()),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive network boundary
            self.audit.write(
                {
                    "timestamp": utc_now_iso(),
                    "module": "local_worker",
                    "event": "heartbeat_failed",
                    "phase": phase,
                    "error": redact_payload(_unexpected_reporting_error(exc).to_dict()),
                }
            )

    async def _record_task_failure(self, task: dict[str, object], error: ErrorEnvelope) -> None:
        task_id = _task_id(task)
        run_id = new_id("run")
        error_payload = redact_payload(error.to_dict())
        self.audit.write(
            {
                "timestamp": utc_now_iso(),
                "module": "local_worker",
                "event": "task_failed",
                "task_id": task_id,
                "run_id": run_id,
                "task": redact_payload(task),
                "error": error_payload,
            }
        )
        if task_id == "unknown":
            return

        failure_event = RunEvent(
            task_id=task_id,
            run_id=run_id,
            agent="local_worker",
            event_type=EventType.RUN_FAILED,
            summary="Task failed inside local worker isolation boundary",
            risk_level=RiskLevel.LOW,
            details={"error": error_payload},
        )
        self.audit.write(failure_event.to_dict())
        await self._best_effort_report_failure(task_id, failure_event)

    async def _best_effort_report_failure(self, task_id: str, event: RunEvent) -> None:
        try:
            await self.client.post_event(event)
        except SafeAgentError as exc:
            self._audit_reporting_failure("post_event", task_id, exc.envelope)
        except Exception as exc:  # pragma: no cover - defensive network boundary
            self._audit_reporting_failure("post_event", task_id, _unexpected_reporting_error(exc))

        try:
            await self.client.update_status(task_id, TaskStatus.FAILED)
        except SafeAgentError as exc:
            self._audit_reporting_failure("update_status", task_id, exc.envelope)
        except Exception as exc:  # pragma: no cover - defensive network boundary
            self._audit_reporting_failure("update_status", task_id, _unexpected_reporting_error(exc))

    def _audit_reporting_failure(self, operation: str, task_id: str, error: ErrorEnvelope) -> None:
        self.audit.write(
            {
                "timestamp": utc_now_iso(),
                "module": "local_worker",
                "event": "task_failure_report_failed",
                "operation": operation,
                "task_id": task_id,
                "error": redact_payload(error.to_dict()),
            }
        )


def _task_id(task: dict[str, object]) -> str:
    value = task.get("task_id")
    return str(value) if value else "unknown"


def _unexpected_reporting_error(exc: Exception) -> ErrorEnvelope:
    return ErrorEnvelope(
        code="worker.report_failed",
        module="local_worker.worker",
        message="Failed to report isolated task failure",
        severity=Severity.ERROR,
        retriable=True,
        details={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
        },
    )


async def async_main() -> None:
    worker = LocalWorker(WorkerSettings.from_env())
    await worker.run_forever()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
