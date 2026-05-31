from __future__ import annotations

import asyncio

from safeagent.local_worker.client import ControlPlaneClient
from safeagent.local_worker.orchestrator import LocalOrchestrator
from safeagent.local_worker.policy import PolicyEngine
from safeagent.local_worker.providers import build_provider_registry
from safeagent.local_worker.registry import load_default_registries
from safeagent.local_worker.settings import WorkerSettings
from safeagent.shared.audit_log import JsonlAuditLog
from safeagent.shared.errors import SafeAgentError
from safeagent.shared.redaction import redact_payload
from safeagent.shared.time import utc_now_iso


class LocalWorker:
    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.audit = JsonlAuditLog(settings.logs_dir / "worker.jsonl")
        self.client = ControlPlaneClient(settings.control_url, settings.token)
        agent_registry, profile_registry = load_default_registries(settings.config_dir)
        provider_registry = build_provider_registry(
            local_qwen_base_url=settings.local_qwen_base_url,
            local_qwen_model=settings.local_qwen_model,
            local_qwen_api_key=settings.local_qwen_api_key,
            deepseek_base_url=settings.deepseek_base_url,
            deepseek_model=settings.deepseek_model,
            deepseek_api_key=settings.deepseek_api_key,
            codex_base_url=settings.codex_base_url,
            codex_model=settings.codex_model,
            codex_api_key=settings.codex_api_key,
            timeout_seconds=settings.model_timeout_seconds,
        )
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
        tasks = await self.client.fetch_pending(self.settings.device_id)
        for task in tasks:
            await self._handle_task(task)
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


async def async_main() -> None:
    worker = LocalWorker(WorkerSettings.from_env())
    await worker.run_forever()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
