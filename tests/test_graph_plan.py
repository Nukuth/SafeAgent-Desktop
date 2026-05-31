from pathlib import Path

from safeagent.local_worker.graph_plan import GraphPlanCompiler
from safeagent.local_worker.registry import AgentRegistry, ProfileEdge, ProfileSpec, load_default_registries
from safeagent.shared.enums import NetworkMode
from safeagent.shared.errors import ValidationError


def test_compile_default_safe_shell_graph():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    assert graph.entry == "planner"
    assert graph.terminal_nodes == ("summarizer",)
    assert any(edge.condition == "approved" for edge in graph.edges)


def test_graph_rejects_edge_to_unknown_node():
    agents, profiles = load_default_registries(Path("configs"))
    profile = ProfileSpec(
        profile_id="bad",
        network_mode=NetworkMode.API_ONLY,
        remote_allowed=True,
        nodes=("planner",),
        entry="planner",
        edges=(ProfileEdge(source="planner", target="missing"),),
    )
    try:
        GraphPlanCompiler(agents).compile(profile)
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert "unknown node" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")


def test_graph_rejects_unreachable_node():
    agents, profiles = load_default_registries(Path("configs"))
    profile = ProfileSpec(
        profile_id="bad",
        network_mode=NetworkMode.API_ONLY,
        remote_allowed=True,
        nodes=("planner", "shell_agent", "summarizer"),
        entry="planner",
        edges=(ProfileEdge(source="planner", target="shell_agent"),),
    )
    try:
        GraphPlanCompiler(agents).compile(profile)
    except ValidationError as exc:
        assert "unreachable" in exc.envelope.message
        assert "summarizer" in str(exc.envelope.details)
    else:
        raise AssertionError("expected ValidationError")

