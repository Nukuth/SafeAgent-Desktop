from datetime import UTC, datetime, timedelta
from pathlib import Path

from safeagent.local_worker.orchestrator import LocalOrchestrator
from safeagent.local_worker.policy import PolicyEngine
from safeagent.local_worker.providers import build_provider_registry
from safeagent.local_worker.registry import load_default_registries
from safeagent.shared.enums import TaskStatus


def test_orchestrator_dry_runs_low_risk_task():
    orchestrator = LocalOrchestrator(PolicyEngine(Path("E:/agents")))
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "查看 E:\\agents 状态", "requested_profile": "safe_shell"}
    )
    assert result.status == TaskStatus.COMPLETED
    assert any(event.event_type.value == "run_completed" for event in result.events)
    assert any(event.event_type.value == "command_proposed" for event in result.events)
    assert any(event.event_type.value == "command_validated" for event in result.events)
    profile_events = [event for event in result.events if event.agent == "topology_router"]
    policy_events = [event for event in result.events if event.agent == "policy_engine"]
    assert profile_events[0].details["command_hash"] == policy_events[0].details["command_hash"]


def test_orchestrator_blocks_high_risk_task():
    orchestrator = LocalOrchestrator(PolicyEngine(Path("E:/agents")))
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "执行 diskpart 修改分区", "requested_profile": "safe_shell"}
    )
    assert result.status == TaskStatus.BLOCKED
    assert result.policy.allowed is False


def test_orchestrator_uses_registry_profile_network_mode():
    agents, profiles = load_default_registries(Path("configs"))
    orchestrator = LocalOrchestrator(PolicyEngine(Path("E:/agents")), agents, profiles)
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "查找论文资料", "requested_profile": "research"}
    )
    assert result.status == TaskStatus.COMPLETED
    route_events = [event for event in result.events if event.agent == "model_router"]
    assert route_events
    assert route_events[0].network_mode.value == "search_allowed"
    profile_events = [event for event in result.events if event.agent == "topology_router"]
    assert profile_events[0].details["graph"]["entry"] == "planner"
    graph_events = [event for event in result.events if event.agent == "graph_runner"]
    assert graph_events
    assert graph_events[0].details["status"] == "completed"
    assert graph_events[0].details["runtime"] in {"langgraph", "stdlib"}
    node_results = graph_events[0].details["node_results"]
    assert any(item["node_id"] == "search_agent" for item in node_results)


def test_orchestrator_can_force_stdlib_graph_runtime():
    agents, profiles = load_default_registries(Path("configs"))
    orchestrator = LocalOrchestrator(
        PolicyEngine(Path("E:/agents")),
        agents,
        profiles,
        graph_runtime="stdlib",
    )
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "check E:\\agents", "requested_profile": "safe_shell"}
    )
    graph_events = [event for event in result.events if event.agent == "graph_runner"]
    assert graph_events[0].details["runtime"] == "stdlib"
    profile_events = [event for event in result.events if event.agent == "topology_router"]
    assert profile_events[0].details["graph_runtime"] == "stdlib"


def test_orchestrator_uses_local_qwen_route_in_emergency_mode():
    agents, profiles = load_default_registries(Path("configs"))
    orchestrator = LocalOrchestrator(
        PolicyEngine(Path("E:/agents")),
        agents,
        profiles,
        emergency_local_model=True,
    )
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "查看 E:\\agents 状态", "requested_profile": "safe_shell"}
    )
    route_events = [event for event in result.events if event.agent == "model_router"]
    assert route_events[0].details["primary_model"] == "local_qwen"


def test_orchestrator_reports_provider_status_without_api_key():
    agents, profiles = load_default_registries(Path("configs"))
    providers = build_provider_registry(
        local_qwen_base_url="http://127.0.0.1:8000/v1",
        local_qwen_model="qwen-35b-local",
        local_qwen_api_key="local-no-key",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        deepseek_api_key="secret-deepseek-key",
        codex_base_url="https://codex.example/v1",
        codex_model="codex",
        codex_api_key="secret-codex-key",
        timeout_seconds=60,
    )
    orchestrator = LocalOrchestrator(
        PolicyEngine(Path("E:/agents")),
        agents,
        profiles,
        provider_registry=providers,
    )
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "查看 E:\\agents 状态", "requested_profile": "safe_shell"}
    )
    route_events = [event for event in result.events if event.agent == "model_router"]
    details = route_events[0].details
    assert details["provider_status"]["deepseek"]["has_api_key"] is True
    assert "secret-deepseek-key" not in str(details)
    assert "secret-codex-key" not in str(details)


def test_orchestrator_waits_for_medium_risk_approval():
    orchestrator = LocalOrchestrator(PolicyEngine(Path("E:/agents")))
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "copy-item E:\\agents\\a E:\\agents\\b", "requested_profile": "safe_shell"}
    )
    assert result.status == TaskStatus.WAITING_APPROVAL
    approval_events = [event for event in result.events if event.agent == "human_approval"]
    assert approval_events[-1].event_type.value == "approval_requested"
    assert approval_events[-1].details["plan_hash"] == result.plan_hash
    assert "command_hash" in approval_events[-1].details


def test_orchestrator_rejects_mismatched_approval():
    orchestrator = LocalOrchestrator(PolicyEngine(Path("E:/agents")))
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "copy-item E:\\agents\\a E:\\agents\\b", "requested_profile": "safe_shell"},
        approval={
            "approval_id": "approval_1",
            "decision": "approved",
            "plan_hash": "old-plan",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        },
    )
    assert result.status == TaskStatus.REJECTED
    approval_events = [event for event in result.events if event.agent == "human_approval"]
    assert "plan_hash" in approval_events[-1].details["reason"]


def test_orchestrator_accepts_valid_approval_for_current_plan():
    agents, profiles = load_default_registries(Path("configs"))
    orchestrator = LocalOrchestrator(PolicyEngine(Path("E:/agents")), agents, profiles)
    task = {
        "task_id": "task_1",
        "content": "copy-item E:\\agents\\a E:\\agents\\b",
        "requested_profile": "safe_shell",
    }
    first = orchestrator.handle_task(task)
    second = orchestrator.handle_task(
        task,
        approval={
            "approval_id": "approval_1",
            "decision": "approved",
            "approved_by": "user",
            "approval_scope": "plan_only",
            "plan_hash": first.plan_hash,
            "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        },
    )
    assert second.status == TaskStatus.COMPLETED
    approval_events = [event for event in second.events if event.event_type.value == "approval_recorded"]
    assert approval_events
    assert approval_events[-1].details["plan_hash"] == first.plan_hash
    assert approval_events[-1].details["command_hash"]
    graph_events = [event for event in second.events if event.agent == "graph_runner"]
    node_ids = [item["node_id"] for item in graph_events[0].details["node_results"]]
    assert "human_approval" in node_ids
    assert "executor" in node_ids


def test_orchestrator_live_readonly_requires_approval_before_execution():
    orchestrator = LocalOrchestrator(
        PolicyEngine(Path("E:/agents")),
        execution_mode="live_readonly",
        enable_live_readonly=True,
    )
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "查看 E:\\agents 状态", "requested_profile": "safe_shell"}
    )
    assert result.status == TaskStatus.WAITING_APPROVAL
    command_events = [event for event in result.events if event.agent == "executor"]
    assert command_events[0].details["dry_run_only"] is False
    assert all("executed" not in event.details for event in command_events)
    approval_events = [event for event in result.events if event.agent == "human_approval"]
    assert approval_events[-1].details["execution_requires_approval"] is True


def test_orchestrator_live_readonly_disabled_blocks_execution_mode():
    orchestrator = LocalOrchestrator(
        PolicyEngine(Path("E:/agents")),
        execution_mode="live_readonly",
        enable_live_readonly=False,
    )
    result = orchestrator.handle_task(
        {"task_id": "task_1", "content": "查看 E:\\agents 状态", "requested_profile": "safe_shell"}
    )
    assert result.status == TaskStatus.BLOCKED
    skipped_events = [event for event in result.events if event.event_type.value == "execution_skipped"]
    assert "SAFEAGENT_ENABLE_LIVE_READONLY" in str(skipped_events[-1].details)
