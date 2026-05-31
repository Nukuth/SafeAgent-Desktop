from __future__ import annotations

from dataclasses import dataclass

from safeagent.local_worker.executor import CommandProposal, CommandValidator, DryRunExecutor, command_fingerprint
from safeagent.local_worker.graph_plan import GraphPlan, GraphPlanCompiler
from safeagent.local_worker.graph_runner import GraphState
from safeagent.local_worker.graph_runtime import (
    build_graph_runner,
    GraphRuntime,
    parse_graph_runtime,
    resolved_graph_runtime_name,
)
from safeagent.local_worker.model_router import ModelRouter
from safeagent.local_worker.node_handlers import build_default_handlers
from safeagent.local_worker.policy import PolicyDecision, PolicyEngine
from safeagent.local_worker.providers import ProviderRegistry
from safeagent.local_worker.registry import AgentRegistry, ProfileRegistry
from safeagent.shared.enums import EventType, NetworkMode, TaskStatus
from safeagent.shared.approval import check_approval
from safeagent.shared.errors import ValidationError
from safeagent.shared.ids import new_id
from safeagent.shared.plan_hash import compute_plan_hash
from safeagent.shared.schemas import RunEvent


@dataclass(slots=True)
class OrchestratorResult:
    run_id: str
    status: TaskStatus
    events: list[RunEvent]
    policy: PolicyDecision
    plan_hash: str


class LocalOrchestrator:
    """MVP orchestrator that selects a safe placeholder profile and runs policy gates.

    Later versions should compile Profile Registry entries into LangGraph graphs.
    This class already returns stable events so the server and logs do not need
    to change when LangGraph is added.
    """

    def __init__(
        self,
        policy_engine: PolicyEngine,
        agent_registry: AgentRegistry | None = None,
        profile_registry: ProfileRegistry | None = None,
        model_router: ModelRouter | None = None,
        provider_registry: ProviderRegistry | None = None,
        emergency_local_model: bool = False,
        execution_mode: str = "dry_run",
        execution_timeout_seconds: float = 30.0,
        stdout_limit_chars: int = 4000,
        stderr_limit_chars: int = 4000,
        enable_live_readonly: bool = False,
        graph_runtime: str | GraphRuntime = GraphRuntime.AUTO,
    ) -> None:
        self.policy_engine = policy_engine
        self.agent_registry = agent_registry
        self.profile_registry = profile_registry
        self.model_router = model_router or ModelRouter()
        self.provider_registry = provider_registry or ProviderRegistry()
        self.emergency_local_model = emergency_local_model
        self.execution_mode = execution_mode
        self.enable_live_readonly = enable_live_readonly
        self.graph_runtime = (
            graph_runtime if isinstance(graph_runtime, GraphRuntime) else parse_graph_runtime(str(graph_runtime))
        )
        self.resolved_graph_runtime = resolved_graph_runtime_name(self.graph_runtime)
        self.executor = DryRunExecutor(
            CommandValidator(
                policy_engine.workspace_root,
                policy_engine,
                allow_live_readonly=enable_live_readonly,
            ),
            execution_mode=execution_mode,
            timeout_seconds=execution_timeout_seconds,
            stdout_limit_chars=stdout_limit_chars,
            stderr_limit_chars=stderr_limit_chars,
        )
        self.graph_compiler = GraphPlanCompiler(agent_registry) if agent_registry else None
        self.graph_runner = build_graph_runner(
            self.graph_runtime,
            build_default_handlers(self.provider_registry),
        )

    def handle_task(
        self,
        task: dict[str, object],
        approval: dict[str, object] | None = None,
    ) -> OrchestratorResult:
        run_id = new_id("run")
        task_id = str(task["task_id"])
        content = str(task["content"])
        profile = self._resolve_profile(str(task.get("requested_profile") or ""), content)
        network_mode = self._network_mode_for_profile(profile)
        policy = self.policy_engine.evaluate_task(content, network_mode=network_mode)
        route = self._route_for_profile(profile, policy)
        graph_plan = self._compile_graph_plan(profile)
        command_proposal = self._propose_readonly_command(profile)
        command_hash = command_fingerprint(command_proposal)
        command_validation = self.executor.validator.validate(command_proposal, execution_mode=self.execution_mode)
        execution_requires_approval = self.execution_mode != "dry_run"
        plan = {
            "task_id": task_id,
            "content": content,
            "profile": profile,
            "graph": graph_plan.to_dict() if graph_plan else None,
            "network_mode": network_mode.value,
            "policy": policy.to_dict(),
            "model_route": route.to_dict(),
            "execution_mode": self.execution_mode,
            "graph_runtime": self.resolved_graph_runtime,
            "live_readonly_enabled": self.enable_live_readonly,
            "execution_requires_approval": execution_requires_approval,
            "command": command_proposal.to_dict(),
            "command_hash": command_hash,
        }
        plan_hash = compute_plan_hash(plan)
        prechecked_approval = None
        if approval and (policy.requires_local_confirmation or execution_requires_approval):
            prechecked_approval = check_approval(
                decision=str(approval.get("decision")) if approval else None,
                approval_plan_hash=str(approval.get("plan_hash")) if approval and approval.get("plan_hash") else None,
                expected_plan_hash=plan_hash,
                expires_at=str(approval.get("expires_at")) if approval and approval.get("expires_at") else None,
            )
        graph_payload = dict(plan)
        if prechecked_approval and prechecked_approval.valid:
            graph_payload["approval_valid"] = True
        graph_result = (
            self.graph_runner.run(graph_plan, GraphState(task_id=task_id, run_id=run_id, payload=graph_payload))
            if graph_plan
            else None
        )

        events = [
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="topology_router",
                event_type=EventType.PROFILE_SELECTED,
                summary=f"Selected profile {profile}",
                risk_level=policy.risk_level,
                network_mode=network_mode,
                details={
                    "profile": profile,
                    "plan_hash": plan_hash,
                    "command_hash": command_hash,
                    "graph": graph_plan.to_dict() if graph_plan else None,
                    "graph_runtime": self.resolved_graph_runtime,
                },
            ),
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="graph_runner",
                event_type=EventType.GRAPH_RUN_COMPLETED
                if not graph_result or graph_result.status == "completed"
                else EventType.GRAPH_NODE_FAILED,
                summary="Graph runner completed placeholder node trace"
                if not graph_result or graph_result.status == "completed"
                else "Graph runner stopped on node failure",
                risk_level=policy.risk_level,
                network_mode=network_mode,
                details={
                    **(graph_result.to_dict() if graph_result else {"status": "skipped"}),
                    "runtime": self.resolved_graph_runtime,
                },
            ),
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="shell_agent",
                event_type=EventType.COMMAND_PROPOSED,
                summary="Generated read-only command proposal",
                risk_level=command_proposal.expected_risk,
                network_mode=network_mode,
                details=command_proposal.to_dict(),
            ),
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="executor",
                event_type=EventType.COMMAND_VALIDATED,
                summary="Validated command proposal before execution",
                risk_level=policy.risk_level,
                network_mode=network_mode,
                details=command_validation.to_dict(),
            ),
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="model_router",
                event_type=EventType.MODEL_ROUTE_SELECTED,
                summary=f"Selected primary model {route.primary_model}",
                risk_level=policy.risk_level,
                network_mode=network_mode,
                details={
                    **route.to_dict(),
                    "provider_status": self._provider_status_for_route(route.primary_model, route.review_model),
                },
            ),
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="policy_engine",
                event_type=EventType.POLICY_DECISION,
                summary="Local policy decision completed",
                risk_level=policy.risk_level,
                network_mode=network_mode,
                details={**policy.to_dict(), "plan_hash": plan_hash, "command_hash": command_hash},
            ),
        ]

        if graph_result and graph_result.status == "failed":
            events.append(
                RunEvent(
                    task_id=task_id,
                    run_id=run_id,
                    agent="graph_runner",
                    event_type=EventType.RUN_FAILED,
                    summary="Graph placeholder execution failed before command validation",
                    risk_level=policy.risk_level,
                    network_mode=network_mode,
                    details=graph_result.to_dict(),
                )
            )
            return OrchestratorResult(run_id, TaskStatus.FAILED, events, policy, plan_hash)

        if not command_validation.allowed:
            events.append(
                RunEvent(
                    task_id=task_id,
                    run_id=run_id,
                    agent="executor",
                    event_type=EventType.EXECUTION_SKIPPED,
                    summary="Execution blocked by command validation",
                    risk_level=command_validation.risk_level,
                    network_mode=network_mode,
                    details={"validation": command_validation.to_dict(), "plan_hash": plan_hash},
                )
            )
            return OrchestratorResult(run_id, TaskStatus.BLOCKED, events, policy, plan_hash)

        if not policy.allowed:
            events.append(
                RunEvent(
                    task_id=task_id,
                    run_id=run_id,
                    agent="executor",
                    event_type=EventType.EXECUTION_SKIPPED,
                    summary="Execution blocked by local policy",
                    risk_level=policy.risk_level,
                    network_mode=network_mode,
                    details={**policy.to_dict(), "plan_hash": plan_hash, "command_hash": command_hash},
                )
            )
            return OrchestratorResult(run_id, TaskStatus.BLOCKED, events, policy, plan_hash)

        if policy.requires_local_confirmation or execution_requires_approval:
            approval_check = prechecked_approval or check_approval(
                decision=str(approval.get("decision")) if approval else None,
                approval_plan_hash=str(approval.get("plan_hash")) if approval and approval.get("plan_hash") else None,
                expected_plan_hash=plan_hash,
                expires_at=str(approval.get("expires_at")) if approval and approval.get("expires_at") else None,
            )
            if approval_check.valid:
                events.append(
                    RunEvent(
                        task_id=task_id,
                        run_id=run_id,
                        agent="executor",
                        event_type=EventType.COMMAND_VALIDATED,
                        summary="Command execution completed through gated executor",
                        risk_level=command_validation.risk_level,
                        network_mode=network_mode,
                        details=self.executor.execute(command_proposal).to_dict(),
                    )
                )
                events.append(
                    RunEvent(
                        task_id=task_id,
                        run_id=run_id,
                        agent="human_approval",
                        event_type=EventType.APPROVAL_RECORDED,
                        summary="Valid approval matched current plan",
                        risk_level=policy.risk_level,
                        network_mode=network_mode,
                        details={
                            "approval_id": approval.get("approval_id") if approval else None,
                            "approved_by": approval.get("approved_by") if approval else None,
                            "approval_scope": approval.get("approval_scope") if approval else None,
                            "reason": approval_check.reason,
                            "plan_hash": plan_hash,
                            "command_hash": command_hash,
                        },
                    )
                )
                events.append(
                    RunEvent(
                        task_id=task_id,
                        run_id=run_id,
                        agent="summarizer",
                        event_type=EventType.RUN_COMPLETED,
                        summary="MVP accepted approval and completed dry-run; no command execution performed",
                        risk_level=policy.risk_level,
                        network_mode=network_mode,
                        details={
                            "execution_mode": self.execution_mode,
                            "plan_hash": plan_hash,
                            "command_hash": command_hash,
                        },
                    )
                )
                return OrchestratorResult(run_id, TaskStatus.COMPLETED, events, policy, plan_hash)
            if approval:
                events.append(
                    RunEvent(
                        task_id=task_id,
                        run_id=run_id,
                        agent="human_approval",
                        event_type=EventType.EXECUTION_SKIPPED,
                        summary="Approval rejected by local validation",
                        risk_level=policy.risk_level,
                        network_mode=network_mode,
                        details={
                            "reason": approval_check.reason,
                            "approval_id": approval.get("approval_id"),
                            "plan_hash": plan_hash,
                            "command_hash": command_hash,
                        },
                    )
                )
                return OrchestratorResult(run_id, TaskStatus.REJECTED, events, policy, plan_hash)
            events.append(
                RunEvent(
                    task_id=task_id,
                    run_id=run_id,
                    agent="human_approval",
                    event_type=EventType.APPROVAL_REQUESTED,
                    summary="Local confirmation is required before execution",
                    risk_level=policy.risk_level,
                    network_mode=network_mode,
                    details={
                        **policy.to_dict(),
                        "plan_hash": plan_hash,
                        "command_hash": command_hash,
                        "execution_requires_approval": execution_requires_approval,
                    },
                )
            )
            return OrchestratorResult(run_id, TaskStatus.WAITING_APPROVAL, events, policy, plan_hash)

        execution_result = self.executor.execute(command_proposal)
        events.append(
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="executor",
                event_type=EventType.COMMAND_VALIDATED,
                summary="Command execution completed through gated executor",
                risk_level=execution_result.validation.risk_level,
                network_mode=network_mode,
                details=execution_result.to_dict(),
            )
        )
        events.append(
            RunEvent(
                task_id=task_id,
                run_id=run_id,
                agent="summarizer",
                event_type=EventType.RUN_COMPLETED,
                summary="MVP completed policy-only dry run; no command execution performed",
                risk_level=policy.risk_level,
                network_mode=network_mode,
                details={"execution_mode": self.execution_mode, "plan_hash": plan_hash, "command_hash": command_hash},
            )
        )
        return OrchestratorResult(run_id, TaskStatus.COMPLETED, events, policy, plan_hash)

    def _resolve_profile(self, requested_profile: str, content: str) -> str:
        if requested_profile:
            if self.profile_registry and not self.profile_registry.has(requested_profile):
                raise ValidationError(
                    "local_worker.orchestrator",
                    f"Requested profile does not exist: {requested_profile}",
                    {"requested_profile": requested_profile},
                )
            return requested_profile
        return self._select_profile(content)

    def _select_profile(self, content: str) -> str:
        text = content.lower()
        if "搜索" in text or "research" in text or "查找论文" in text:
            return "research"
        if "整理" in text or "文件" in text:
            return "file_organize"
        if "代码" in text or "code" in text:
            return "code_change"
        return "safe_shell"

    def _network_mode_for_profile(self, profile: str) -> NetworkMode:
        if self.profile_registry:
            return self.profile_registry.get(profile).network_mode
        if profile == "research":
            return NetworkMode.SEARCH_ALLOWED
        return NetworkMode.API_ONLY

    def _route_for_profile(self, profile: str, policy: PolicyDecision):
        if not self.profile_registry or not self.agent_registry:
            return self.model_router.route(
                model_policy="deepseek_default",
                risk_level=policy.risk_level,
                emergency_local=self.emergency_local_model,
            )
        profile_spec = self.profile_registry.get(profile)
        model_policy = "deepseek_default"
        for node in profile_spec.nodes:
            agent = self.agent_registry.get(node)
            if agent.model_policy != "none":
                model_policy = agent.model_policy
                break
        return self.model_router.route(
            model_policy=model_policy,
            risk_level=policy.risk_level,
            emergency_local=self.emergency_local_model,
        )

    def _compile_graph_plan(self, profile: str) -> GraphPlan | None:
        if not self.profile_registry or not self.graph_compiler:
            return None
        return self.graph_compiler.compile(self.profile_registry.get(profile))

    def _propose_readonly_command(self, profile: str) -> CommandProposal:
        if profile == "research":
            return CommandProposal(
                command="Get-ChildItem",
                args=("E:\\agents",),
                cwd="E:\\agents",
                reason="MVP placeholder; research profile does not execute web search yet",
            )
        return CommandProposal(
            command="Get-ChildItem",
            args=("E:\\agents",),
            cwd="E:\\agents",
            reason="MVP placeholder read-only workspace inspection",
        )

    def _provider_status_for_route(self, primary_model: str, review_model: str | None) -> dict[str, object]:
        public_status = self.provider_registry.public_status()
        models = [primary_model]
        if review_model:
            models.append(review_model)
        status: dict[str, object] = {}
        for model in models:
            status[model] = public_status.get(
                model,
                {
                    "provider_id": model,
                    "configured": False,
                    "has_api_key": False,
                },
            )
        return status
