from __future__ import annotations

from importlib.util import find_spec
from typing import Any, Callable

from safeagent.local_worker.graph_plan import GraphEdge, GraphPlan, GraphNode
from safeagent.local_worker.graph_runner import (
    EdgeDecision,
    GraphRunResult,
    GraphState,
    NodeHandler,
    NodeResult,
)
from safeagent.local_worker.langgraph_state import initial_langgraph_state, SafeAgentState
from safeagent.shared.enums import RiskLevel
from safeagent.shared.errors import DependencyMissingError, ErrorEnvelope, SafeAgentError, ValidationError
from safeagent.shared.graph_conditions import APPROVED, REVIEW_PASSED, risk_condition_matches

MODULE = "local_worker.langgraph_adapter"


class LangGraphRunner:
    """Optional LangGraph-backed runner with GraphRunner-compatible output."""

    def __init__(
        self,
        handlers: dict[str, NodeHandler] | None = None,
        *,
        checkpointer: object | None = None,
    ) -> None:
        self.handlers = handlers or {}
        self.checkpointer = checkpointer

    def run(self, graph: GraphPlan, state: GraphState) -> GraphRunResult:
        compiled = compile_langgraph_graph(
            graph,
            self.handlers,
            checkpointer=self.checkpointer,
        )
        result = compiled.invoke(
            initial_langgraph_state(
                task_id=state.task_id,
                run_id=state.run_id,
                profile_id=graph.profile_id,
                payload=state.payload,
            )
        )
        return langgraph_result_to_graph_run_result(graph.profile_id, result)


def langgraph_available() -> bool:
    return find_spec("langgraph") is not None


def require_langgraph() -> None:
    if not langgraph_available():
        raise DependencyMissingError(
            MODULE,
            "langgraph",
            "Install the LangGraph extra before enabling the LangGraph runtime.",
        )


def assert_langgraph_safety_contract(graph: GraphPlan) -> None:
    """Validate invariants that must hold before compiling a LangGraph graph."""

    node_ids = {node.node_id for node in graph.nodes}
    if "executor" in node_ids:
        approved_edges = [
            edge
            for edge in graph.edges
            if edge.source == "human_approval" and edge.target == "executor" and edge.condition == "approved"
        ]
        if not approved_edges:
            raise ValidationError(
                MODULE,
                "LangGraph executor route must preserve human approval gate",
                {"profile_id": graph.profile_id},
            )
    unsafe_executor_edges = [
        edge
        for edge in graph.edges
        if edge.target == "executor" and edge.source not in {"rule_reviewer", "human_approval"}
    ]
    if unsafe_executor_edges:
        raise ValidationError(
            MODULE,
            "LangGraph executor route may only come from rule_reviewer or human_approval",
            {
                "profile_id": graph.profile_id,
                "edges": [
                    {"from": edge.source, "to": edge.target, "condition": edge.condition}
                    for edge in unsafe_executor_edges
                ],
            },
        )


def make_langgraph_node(
    node: GraphNode,
    handler: NodeHandler,
    outgoing_edges: tuple[GraphEdge, ...] = (),
) -> Callable[[SafeAgentState], dict[str, Any]]:
    """Wrap a SafeAgent node handler as a LangGraph node.

    The wrapper is intentionally side-effect free. It adapts state and records
    node output, but does not call shell, network, server code, or file writes.
    """

    def run_node(state: SafeAgentState) -> dict[str, Any]:
        from langgraph.graph import END
        from langgraph.types import Command

        try:
            output = handler(
                node,
                GraphState(
                    task_id=str(state["task_id"]),
                    run_id=str(state["run_id"]),
                    payload=dict(state.get("payload", {})),
                ),
            )
            result = NodeResult(node.node_id, "completed", output=output)
            node_outputs = dict(state.get("node_outputs", {}))
            node_outputs[node.node_id] = output
            next_nodes, edge_decisions = choose_next_nodes(outgoing_edges, state, node_outputs)
            goto: str | list[str] = next_nodes if next_nodes else END
            if len(next_nodes) == 1:
                goto = next_nodes[0]
            return Command(
                goto=goto,
                update={
                    "node_results": [result.to_dict()],
                    "node_outputs": {node.node_id: output},
                    "edge_decisions": edge_decisions,
                    "status": "running",
                },
            )
        except SafeAgentError as exc:
            result = NodeResult(node.node_id, "failed", error=exc.envelope)
            return Command(
                goto=END,
                update={
                    "node_results": [result.to_dict()],
                    "status": "failed",
                    "error": exc.envelope.to_dict(),
                },
            )
        except Exception as exc:
            wrapped = ValidationError(
                MODULE,
                f"LangGraph node {node.node_id} failed with unexpected error",
                {"node_id": node.node_id, "error": str(exc)},
            )
            result = NodeResult(node.node_id, "failed", error=wrapped.envelope)
            return Command(
                goto=END,
                update={
                    "node_results": [result.to_dict()],
                    "status": "failed",
                    "error": wrapped.envelope.to_dict(),
                },
            )

    return run_node


def compile_langgraph_graph(
    graph: GraphPlan,
    handlers: dict[str, NodeHandler] | None = None,
    *,
    checkpointer: object | None = None,
):
    """Compile a GraphPlan into a LangGraph StateGraph.

    This function is optional at runtime. It raises dependency.missing when
    LangGraph is not installed, and it rechecks the SafeAgent safety contract
    before compiling.
    """

    require_langgraph()
    assert_langgraph_safety_contract(graph)

    from langgraph.graph import START, StateGraph

    handlers = handlers or {}
    builder = StateGraph(SafeAgentState)
    edges_by_source = _edges_by_source(graph)
    node_by_id = {node.node_id: node for node in graph.nodes}

    for node in graph.nodes:
        outgoing = tuple(edges_by_source.get(node.node_id, ()))
        destinations = tuple({edge.target for edge in outgoing} | {"__end__"})
        builder.add_node(
            node.node_id,
            make_langgraph_node(
                node,
                handlers.get(node.node_id, _default_handler),
                outgoing,
            ),
            destinations=destinations,
        )

    if graph.entry not in node_by_id:
        raise ValidationError(
            MODULE,
            "LangGraph entry node is missing from graph nodes",
            {"profile_id": graph.profile_id, "entry": graph.entry},
        )
    builder.add_edge(START, graph.entry)
    return builder.compile(checkpointer=checkpointer)


def choose_next_nodes(
    outgoing_edges: tuple[GraphEdge, ...],
    state: SafeAgentState,
    node_outputs: dict[str, dict[str, Any]],
) -> tuple[list[str], list[dict[str, Any]]]:
    next_nodes: list[str] = []
    decisions: list[dict[str, Any]] = []
    for edge in outgoing_edges:
        matches, reason = condition_matches(edge, state, node_outputs)
        decisions.append(
            {
                "from": edge.source,
                "to": edge.target,
                "condition": edge.condition,
                "selected": matches,
                "reason": reason,
            }
        )
        if matches:
            next_nodes.append(edge.target)
    return next_nodes, decisions


def condition_matches(
    edge: GraphEdge,
    state: SafeAgentState,
    node_outputs: dict[str, dict[str, Any]],
) -> tuple[bool, str]:
    condition = edge.condition
    if not condition:
        return True, "unconditional edge"
    risk_level = _risk_level(state)
    risk_match = risk_condition_matches(condition, risk_level)
    if risk_match is not None:
        return risk_match, f"risk_level={risk_level.value}"
    if condition == APPROVED:
        matches = bool(state.get("payload", {}).get("approval_valid"))
        return matches, f"approval_valid={matches}"
    if condition == REVIEW_PASSED:
        source_output = node_outputs.get(edge.source, {})
        review_status = source_output.get("review_status")
        matches = review_status == "passed"
        return matches, f"review_status={review_status or 'missing'}"
    raise ValidationError(
        MODULE,
        f"Unknown graph edge condition: {condition}",
        {"condition": condition, "from": edge.source, "to": edge.target},
    )


def _risk_level(state: SafeAgentState) -> RiskLevel:
    payload = state.get("payload", {})
    policy = payload.get("policy")
    if isinstance(policy, dict):
        raw = policy.get("risk_level")
        if raw:
            return _parse_risk_level(raw)
    raw = payload.get("risk_level")
    if raw:
        return _parse_risk_level(raw)
    return RiskLevel.LOW


def _parse_risk_level(raw: object) -> RiskLevel:
    try:
        return RiskLevel(str(raw))
    except ValueError as exc:
        raise ValidationError(
            MODULE,
            f"Unknown risk level for LangGraph condition routing: {raw}",
            {"risk_level": str(raw)},
        ) from exc


def _edges_by_source(graph: GraphPlan) -> dict[str, list[GraphEdge]]:
    edges: dict[str, list[GraphEdge]] = {}
    for edge in graph.edges:
        edges.setdefault(edge.source, []).append(edge)
    return edges


def _default_handler(node: GraphNode, state: GraphState) -> dict[str, object]:
    return {
        "message": "node placeholder completed",
        "role": node.role,
        "model_policy": node.model_policy,
        "task_id": state.task_id,
    }


def extract_error_envelope(state: SafeAgentState) -> ErrorEnvelope | None:
    error = state.get("error")
    if not isinstance(error, dict):
        return None
    try:
        from safeagent.shared.enums import Severity

        return ErrorEnvelope(
            code=str(error["code"]),
            module=str(error["module"]),
            message=str(error["message"]),
            severity=Severity(str(error.get("severity", "error"))),
            retriable=bool(error.get("retriable", False)),
            details=dict(error.get("details", {})),
        )
    except Exception:
        return ErrorEnvelope(
            code="validation.failed",
            module=MODULE,
            message="LangGraph state contains malformed error envelope",
            details={"error": str(error)},
        )


def langgraph_result_to_graph_run_result(profile_id: str, state: SafeAgentState) -> GraphRunResult:
    node_results = tuple(_node_result_from_dict(item) for item in state.get("node_results", []))
    edge_decisions = tuple(_edge_decision_from_dict(item) for item in state.get("edge_decisions", []))
    error = extract_error_envelope(state)
    status = "failed" if error or state.get("status") == "failed" else "completed"
    return GraphRunResult(profile_id, status, node_results, edge_decisions)


def _node_result_from_dict(item: dict[str, Any]) -> NodeResult:
    raw_error = item.get("error")
    error = None
    if isinstance(raw_error, dict):
        error = extract_error_envelope({"error": raw_error})
    output = item.get("output", {})
    return NodeResult(
        node_id=str(item.get("node_id", "unknown")),
        status=str(item.get("status", "unknown")),
        output=dict(output) if isinstance(output, dict) else {"value": output},
        error=error,
    )


def _edge_decision_from_dict(item: dict[str, Any]) -> EdgeDecision:
    return EdgeDecision(
        source=str(item.get("from", "")),
        target=str(item.get("to", "")),
        condition=str(item["condition"]) if item.get("condition") is not None else None,
        selected=bool(item.get("selected", False)),
        reason=str(item.get("reason", "")),
    )
