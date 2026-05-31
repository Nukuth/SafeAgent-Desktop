from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from safeagent.local_worker.graph_plan import GraphEdge, GraphPlan, GraphNode
from safeagent.shared.enums import RiskLevel
from safeagent.shared.errors import ErrorEnvelope, SafeAgentError, ValidationError
from safeagent.shared.graph_conditions import (
    APPROVED,
    REVIEW_PASSED,
    risk_condition_matches,
)


@dataclass(frozen=True, slots=True)
class GraphState:
    task_id: str
    run_id: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NodeResult:
    node_id: str
    status: str
    output: dict[str, object] = field(default_factory=dict)
    error: ErrorEnvelope | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "status": self.status,
            "output": self.output,
            "error": self.error.to_dict() if self.error else None,
        }


@dataclass(frozen=True, slots=True)
class EdgeDecision:
    source: str
    target: str
    condition: str | None
    selected: bool
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "from": self.source,
            "to": self.target,
            "condition": self.condition,
            "selected": self.selected,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class GraphRunResult:
    profile_id: str
    status: str
    node_results: tuple[NodeResult, ...]
    edge_decisions: tuple[EdgeDecision, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "status": self.status,
            "node_results": [result.to_dict() for result in self.node_results],
            "edge_decisions": [decision.to_dict() for decision in self.edge_decisions],
        }


class NodeHandler(Protocol):
    def __call__(self, node: GraphNode, state: GraphState) -> dict[str, object]:
        ...


class GraphRunner:
    """Standard-library graph runner for MVP traceability.

    It executes nodes by following GraphPlan edges and conservative condition
    checks. The runner does not call shell, network, server code, or write
    files. It only invokes injected node handlers and captures errors.
    """

    def __init__(self, handlers: dict[str, NodeHandler] | None = None) -> None:
        self.handlers = handlers or {}

    def run(self, graph: GraphPlan, state: GraphState) -> GraphRunResult:
        results: list[NodeResult] = []
        edge_decisions: list[EdgeDecision] = []
        node_by_id = {node.node_id: node for node in graph.nodes}
        edges_by_source = self._edges_by_source(graph)
        queue = [graph.entry]
        visited: set[str] = set()
        outputs: dict[str, dict[str, object]] = {}

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_by_id.get(node_id)
            if node is None:
                wrapped = ValidationError(
                    "local_worker.graph_runner",
                    f"Graph edge references missing node {node_id}",
                    {"node_id": node_id},
                )
                results.append(NodeResult(node_id, "failed", error=wrapped.envelope))
                return GraphRunResult(graph.profile_id, "failed", tuple(results), tuple(edge_decisions))
            handler = self.handlers.get(node.node_id, self._default_handler)
            try:
                output = handler(node, state)
            except SafeAgentError as exc:
                results.append(NodeResult(node.node_id, "failed", error=exc.envelope))
                return GraphRunResult(graph.profile_id, "failed", tuple(results), tuple(edge_decisions))
            except Exception as exc:
                wrapped = ValidationError(
                    "local_worker.graph_runner",
                    f"Node {node.node_id} failed with unexpected error",
                    {"node_id": node.node_id, "error": str(exc)},
                )
                results.append(NodeResult(node.node_id, "failed", error=wrapped.envelope))
                return GraphRunResult(graph.profile_id, "failed", tuple(results), tuple(edge_decisions))
            results.append(NodeResult(node.node_id, "completed", output=output))
            outputs[node.node_id] = output

            for edge in edges_by_source.get(node.node_id, []):
                try:
                    matches, reason = self._condition_matches(edge, state, outputs)
                except SafeAgentError as exc:
                    edge_decisions.append(
                        EdgeDecision(edge.source, edge.target, edge.condition, False, exc.envelope.message)
                    )
                    results.append(NodeResult(edge.target, "failed", error=exc.envelope))
                    return GraphRunResult(graph.profile_id, "failed", tuple(results), tuple(edge_decisions))
                edge_decisions.append(EdgeDecision(edge.source, edge.target, edge.condition, matches, reason))
                if matches:
                    queue.append(edge.target)
        return GraphRunResult(graph.profile_id, "completed", tuple(results), tuple(edge_decisions))

    def _edges_by_source(self, graph: GraphPlan) -> dict[str, list[GraphEdge]]:
        edges: dict[str, list[GraphEdge]] = {}
        for edge in graph.edges:
            edges.setdefault(edge.source, []).append(edge)
        return edges

    def _condition_matches(
        self,
        edge: GraphEdge,
        state: GraphState,
        outputs: dict[str, dict[str, object]],
    ) -> tuple[bool, str]:
        condition = edge.condition
        if not condition:
            return True, "unconditional edge"
        risk_level = self._risk_level(state)
        risk_match = risk_condition_matches(condition, risk_level)
        if risk_match is not None:
            matches = risk_match
            return matches, f"risk_level={risk_level.value}"
        if condition == APPROVED:
            matches = bool(state.payload.get("approval_valid"))
            return matches, f"approval_valid={matches}"
        if condition == REVIEW_PASSED:
            source_output = outputs.get(edge.source, {})
            review_status = source_output.get("review_status")
            matches = review_status == "passed"
            return matches, f"review_status={review_status or 'missing'}"
        raise ValidationError(
            "local_worker.graph_runner",
            f"Unknown graph edge condition: {condition}",
            {"condition": condition, "from": edge.source, "to": edge.target},
        )

    def _risk_level(self, state: GraphState) -> RiskLevel:
        policy = state.payload.get("policy")
        if isinstance(policy, dict):
            raw = policy.get("risk_level")
            if raw:
                return self._parse_risk_level(raw)
        raw = state.payload.get("risk_level")
        if raw:
            return self._parse_risk_level(raw)
        return RiskLevel.LOW

    def _parse_risk_level(self, raw: object) -> RiskLevel:
        try:
            return RiskLevel(str(raw))
        except ValueError as exc:
            raise ValidationError(
                "local_worker.graph_runner",
                f"Unknown risk level for graph condition routing: {raw}",
                {"risk_level": str(raw)},
            ) from exc

    def _default_handler(self, node: GraphNode, state: GraphState) -> dict[str, object]:
        return {
            "message": "node placeholder completed",
            "role": node.role,
            "model_policy": node.model_policy,
            "task_id": state.task_id,
        }
