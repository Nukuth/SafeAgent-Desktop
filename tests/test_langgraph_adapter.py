from pathlib import Path

import pytest

from safeagent.local_worker.graph_plan import GraphEdge, GraphPlan, GraphPlanCompiler
from safeagent.local_worker.graph_runner import GraphState
from safeagent.local_worker.langgraph_adapter import (
    assert_langgraph_safety_contract,
    compile_langgraph_graph,
    condition_matches,
    LangGraphRunner,
    langgraph_available,
)
from safeagent.local_worker.langgraph_state import initial_langgraph_state
from safeagent.local_worker.registry import load_default_registries
from safeagent.shared.enums import RiskLevel
from safeagent.shared.errors import ValidationError


def compile_default_graph(profile_id: str):
    agents, profiles = load_default_registries(Path("configs"))
    return GraphPlanCompiler(agents).compile(profiles.get(profile_id))


def test_langgraph_state_initializes_without_side_effects():
    state = initial_langgraph_state(
        task_id="task_1",
        run_id="run_1",
        profile_id="safe_shell",
        payload={"policy": {"risk_level": "low"}},
    )
    assert state["task_id"] == "task_1"
    assert state["node_results"] == []
    assert state["edge_decisions"] == []
    assert state["node_outputs"] == {}
    assert state["status"] == "created"


def test_langgraph_condition_matches_approval_gate():
    state = initial_langgraph_state(
        task_id="task_1",
        run_id="run_1",
        profile_id="safe_shell",
        payload={"policy": {"risk_level": RiskLevel.MEDIUM.value}},
    )
    edge = GraphEdge("human_approval", "executor", "approved")
    assert condition_matches(edge, state, {}) == (False, "approval_valid=False")
    state["payload"]["approval_valid"] = True
    assert condition_matches(edge, state, {}) == (True, "approval_valid=True")


def test_langgraph_safety_contract_rejects_executor_without_approval_edge():
    graph = compile_default_graph("safe_shell")
    unsafe_graph = GraphPlan(
        profile_id=graph.profile_id,
        entry=graph.entry,
        nodes=graph.nodes,
        edges=tuple(edge for edge in graph.edges if edge.source != "human_approval"),
        terminal_nodes=graph.terminal_nodes,
    )
    with pytest.raises(ValidationError) as exc:
        assert_langgraph_safety_contract(unsafe_graph)
    assert "human approval gate" in exc.value.envelope.message


@pytest.mark.skipif(not langgraph_available(), reason="LangGraph is not installed")
def test_compile_langgraph_graph_runs_low_risk_without_approval_branch():
    graph = compile_default_graph("safe_shell")
    compiled = compile_langgraph_graph(graph)
    result = compiled.invoke(
        initial_langgraph_state(
            task_id="task_1",
            run_id="run_1",
            profile_id="safe_shell",
            payload={"policy": {"risk_level": RiskLevel.LOW.value}},
        )
    )
    assert [item["node_id"] for item in result["node_results"]] == [
        "planner",
        "shell_agent",
        "rule_reviewer",
        "executor",
        "summarizer",
    ]
    decisions = {(item["from"], item["to"]): item for item in result["edge_decisions"]}
    assert decisions[("rule_reviewer", "human_approval")]["selected"] is False
    assert decisions[("rule_reviewer", "executor")]["selected"] is True


@pytest.mark.skipif(not langgraph_available(), reason="LangGraph is not installed")
def test_compile_langgraph_graph_waits_at_approval_without_valid_flag():
    graph = compile_default_graph("safe_shell")
    compiled = compile_langgraph_graph(graph)
    result = compiled.invoke(
        initial_langgraph_state(
            task_id="task_1",
            run_id="run_1",
            profile_id="safe_shell",
            payload={"policy": {"risk_level": RiskLevel.MEDIUM.value}},
        )
    )
    assert [item["node_id"] for item in result["node_results"]] == [
        "planner",
        "shell_agent",
        "rule_reviewer",
        "human_approval",
    ]
    decisions = {(item["from"], item["to"]): item for item in result["edge_decisions"]}
    assert decisions[("human_approval", "executor")]["selected"] is False
    assert decisions[("human_approval", "executor")]["reason"] == "approval_valid=False"


@pytest.mark.skipif(not langgraph_available(), reason="LangGraph is not installed")
def test_langgraph_runner_returns_graph_runner_compatible_result():
    graph = compile_default_graph("safe_shell")
    result = LangGraphRunner().run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={"policy": {"risk_level": RiskLevel.LOW.value}},
        ),
    )
    assert result.status == "completed"
    assert [item.node_id for item in result.node_results] == [
        "planner",
        "shell_agent",
        "rule_reviewer",
        "executor",
        "summarizer",
    ]
    decisions = {(item.source, item.target): item for item in result.edge_decisions}
    assert decisions[("rule_reviewer", "human_approval")].selected is False
    assert decisions[("rule_reviewer", "executor")].selected is True
