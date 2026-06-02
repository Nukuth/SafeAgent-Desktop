from __future__ import annotations

from dataclasses import dataclass, replace

from safeagent.local_worker.orchestrator import LocalOrchestrator, OrchestratorResult
from safeagent.local_worker.policy import PolicyEngine
from safeagent.local_worker.providers import ProviderRegistry, build_provider_registry_from_config
from safeagent.local_worker.registry import load_default_registries
from safeagent.local_worker.settings import WorkerSettings
from safeagent.shared.enums import TaskStatus
from safeagent.shared.ids import new_id
from safeagent.shared.redaction import redact_payload


@dataclass(frozen=True, slots=True)
class AgentChatResult:
    reply: str
    status: str
    task_id: str
    run_id: str
    profile: str
    risk_level: str
    model_status: str
    model: str
    plan_hash: str
    execution_status: str
    error: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "reply": self.reply,
            "status": self.status,
            "task_id": self.task_id,
            "run_id": self.run_id,
            "profile": self.profile,
            "risk_level": self.risk_level,
            "model_status": self.model_status,
            "model": self.model,
            "plan_hash": self.plan_hash,
            "execution_status": self.execution_status,
            "error": self.error,
        }


def run_local_agent_chat(
    message: str,
    *,
    requested_profile: str | None = None,
    settings: WorkerSettings | None = None,
    provider_registry: ProviderRegistry | None = None,
    emergency_local_model: bool | None = None,
) -> AgentChatResult:
    settings = settings or WorkerSettings.from_env()
    if emergency_local_model is not None:
        settings = replace(settings, emergency_local_model=emergency_local_model)
    providers = provider_registry or build_provider_registry_from_config(
        settings.config_dir / "models.json",
        env=settings.provider_env,
    )
    agents, profiles = load_default_registries(settings.config_dir)
    orchestrator = LocalOrchestrator(
        PolicyEngine(settings.workspace_root),
        agent_registry=agents,
        profile_registry=profiles,
        provider_registry=providers,
        emergency_local_model=settings.emergency_local_model,
        execution_mode="dry_run",
        graph_runtime=settings.graph_runtime,
    )
    task_id = new_id("task")
    task = {
        "task_id": task_id,
        "content": message,
        "device_id": settings.device_id,
        "requested_profile": requested_profile,
    }
    result = orchestrator.handle_task(task)
    return _chat_result_from_orchestrator(task_id, result)


def _chat_result_from_orchestrator(task_id: str, result: OrchestratorResult) -> AgentChatResult:
    profile = _event_detail(result, "topology_router", "profile") or "unknown"
    model_output = _best_model_output(result)
    model_status = str(model_output.get("model_status", "skipped"))
    model = str(model_output.get("model", "none"))
    error = model_output.get("error") if isinstance(model_output.get("error"), dict) else None
    reply = _reply_text(result, profile, model_output)
    return AgentChatResult(
        reply=reply,
        status=result.status.value,
        task_id=task_id,
        run_id=result.run_id,
        profile=str(profile),
        risk_level=result.policy.risk_level.value,
        model_status=model_status,
        model=model,
        plan_hash=result.plan_hash,
        execution_status=_execution_status(result),
        error=redact_payload(error) if error else None,
    )


def _reply_text(result: OrchestratorResult, profile: object, model_output: dict[str, object]) -> str:
    if not result.policy.allowed:
        return (
            "SafeAgent 已运行，但本地安全策略阻止了这个任务。"
            f"风险等级：{result.policy.risk_level.value}。"
            "我没有执行任何命令。请换成更低风险、更明确的请求。"
        )
    if result.status == TaskStatus.WAITING_APPROVAL:
        return (
            "SafeAgent 已运行，并生成了计划，但这个任务需要人工确认后才能继续。"
            f"profile={profile}，risk={result.policy.risk_level.value}，plan_hash={result.plan_hash}。"
            "我没有执行任何命令。"
        )
    content = model_output.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    error = model_output.get("error")
    if isinstance(error, dict):
        code = str(error.get("code", "unknown"))
        module = str(error.get("module", "unknown"))
        message = str(error.get("message", "model unavailable"))
        return (
            "SafeAgent 已启动并完成本地安全检查，但模型暂时没有可用回复。"
            f"错误：{code}，module={module}，message={message}。"
            "我没有执行任何命令。若要真正对话，请配置 DeepSeek key，或启动本地 Qwen 35B 服务后使用 --local。"
        )
    return (
        "SafeAgent 已启动并完成本地流程。"
        f"profile={profile}，risk={result.policy.risk_level.value}，status={result.status.value}。"
        "当前没有模型文本输出；我没有执行任何命令。"
    )


def _best_model_output(result: OrchestratorResult) -> dict[str, object]:
    fallback: dict[str, object] = {"model_status": "skipped", "model": "none"}
    for output in _node_model_outputs(result):
        if output.get("model_status") == "completed" and output.get("content"):
            return output
        if fallback.get("model_status") == "skipped" and output.get("model_status") != "skipped":
            fallback = output
    return fallback


def _node_model_outputs(result: OrchestratorResult) -> list[dict[str, object]]:
    outputs: list[dict[str, object]] = []
    for event in result.events:
        if event.agent != "graph_runner":
            continue
        node_results = event.details.get("node_results", [])
        if not isinstance(node_results, list):
            continue
        for node_result in node_results:
            if not isinstance(node_result, dict):
                continue
            output = node_result.get("output")
            if not isinstance(output, dict):
                continue
            model = output.get("model")
            if isinstance(model, dict):
                outputs.append(model)
    return outputs


def _event_detail(result: OrchestratorResult, agent: str, key: str) -> object | None:
    for event in result.events:
        if event.agent == agent:
            return event.details.get(key)
    return None


def _execution_status(result: OrchestratorResult) -> str:
    for event in result.events:
        if event.agent == "executor":
            details = event.details
            if "execution" in details:
                return str(details["execution"])
            validation = details.get("validation")
            if isinstance(validation, dict):
                return "validated" if validation.get("allowed") else "blocked"
    return "not_executed"
