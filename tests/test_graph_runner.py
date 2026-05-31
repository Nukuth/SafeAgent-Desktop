from pathlib import Path

from safeagent.local_worker.graph_plan import GraphPlanCompiler
from safeagent.local_worker.graph_runner import GraphRunner, GraphState
from safeagent.local_worker.registry import load_default_registries
from safeagent.shared.enums import RiskLevel
from safeagent.shared.errors import ValidationError


def test_graph_runner_completes_placeholder_nodes():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("research"))
    result = GraphRunner().run(graph, GraphState(task_id="task_1", run_id="run_1"))
    assert result.status == "completed"
    assert [node.node_id for node in graph.nodes] == [item.node_id for item in result.node_results]


def test_graph_runner_stops_on_node_error_with_envelope():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("research"))

    def fail_on_search(node, state):
        if node.node_id == "search_agent":
            raise ValidationError("test", "search failed", {"node": node.node_id})
        return {"ok": True}

    result = GraphRunner({"search_agent": fail_on_search}).run(
        graph,
        GraphState(task_id="task_1", run_id="run_1"),
    )
    assert result.status == "failed"
    assert result.node_results[-1].node_id == "search_agent"
    assert result.node_results[-1].error is not None
    assert result.node_results[-1].error.code == "validation.failed"


def test_graph_runner_skips_approval_branch_for_low_risk():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    result = GraphRunner().run(
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
    assert decisions[("rule_reviewer", "human_approval")].reason == "risk_level=low"
    assert decisions[("rule_reviewer", "executor")].selected is True


def test_graph_runner_waits_at_human_approval_for_medium_without_approval():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    result = GraphRunner().run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={"policy": {"risk_level": RiskLevel.MEDIUM.value}},
        ),
    )
    assert result.status == "completed"
    assert [item.node_id for item in result.node_results] == [
        "planner",
        "shell_agent",
        "rule_reviewer",
        "human_approval",
    ]
    decisions = {(item.source, item.target): item for item in result.edge_decisions}
    assert decisions[("rule_reviewer", "human_approval")].selected is True
    assert decisions[("rule_reviewer", "executor")].selected is False
    assert decisions[("human_approval", "executor")].selected is False
    assert decisions[("human_approval", "executor")].reason == "approval_valid=False"


def test_graph_runner_allows_executor_after_valid_approval_flag():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    result = GraphRunner().run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={"policy": {"risk_level": RiskLevel.MEDIUM.value}, "approval_valid": True},
        ),
    )
    assert result.status == "completed"
    assert [item.node_id for item in result.node_results] == [
        "planner",
        "shell_agent",
        "rule_reviewer",
        "human_approval",
        "executor",
        "summarizer",
    ]
    decisions = {(item.source, item.target): item for item in result.edge_decisions}
    assert decisions[("human_approval", "executor")].selected is True
    assert decisions[("human_approval", "executor")].reason == "approval_valid=True"


def test_graph_runner_does_not_treat_placeholder_review_as_passed():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("code_change"))
    result = GraphRunner().run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={"policy": {"risk_level": RiskLevel.HIGH.value}},
        ),
    )
    assert result.status == "completed"
    assert [item.node_id for item in result.node_results] == [
        "planner",
        "code_agent",
        "test_agent",
        "rule_reviewer",
        "codex_reviewer",
    ]
    decisions = {(item.source, item.target): item for item in result.edge_decisions}
    assert decisions[("codex_reviewer", "human_approval")].selected is False
    assert decisions[("codex_reviewer", "human_approval")].reason in {
        "review_status=missing",
        "review_status=placeholder",
    }


def test_graph_runner_reports_unknown_condition_as_node_failure():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("research"))
    graph = type(graph)(
        profile_id=graph.profile_id,
        entry=graph.entry,
        nodes=graph.nodes,
        edges=(type(graph.edges[0])("planner", "search_agent", "unknown_condition"),),
        terminal_nodes=graph.terminal_nodes,
    )
    result = GraphRunner().run(graph, GraphState(task_id="task_1", run_id="run_1"))
    assert result.status == "failed"
    assert result.node_results[-1].node_id == "search_agent"
    assert result.node_results[-1].error is not None
    assert result.node_results[-1].error.code == "validation.failed"
    assert result.edge_decisions[-1].source == "planner"
    assert result.edge_decisions[-1].target == "search_agent"
    assert result.edge_decisions[-1].selected is False
    assert "Unknown graph edge condition" in result.edge_decisions[-1].reason
