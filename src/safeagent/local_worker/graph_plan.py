from __future__ import annotations

from dataclasses import dataclass

from safeagent.local_worker.registry import AgentRegistry, ProfileEdge, ProfileSpec
from safeagent.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    role: str
    model_policy: str

    def to_dict(self) -> dict[str, str]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "model_policy": self.model_policy,
        }


@dataclass(frozen=True, slots=True)
class GraphEdge:
    source: str
    target: str
    condition: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "from": self.source,
            "to": self.target,
            "condition": self.condition,
        }


@dataclass(frozen=True, slots=True)
class GraphPlan:
    profile_id: str
    entry: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    terminal_nodes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "entry": self.entry,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "terminal_nodes": list(self.terminal_nodes),
        }


class GraphPlanCompiler:
    """Compile a ProfileSpec into a validated graph plan.

    This is deliberately independent of LangGraph so config validation works
    before optional orchestration dependencies are installed.
    """

    def __init__(self, agent_registry: AgentRegistry) -> None:
        self.agent_registry = agent_registry

    def compile(self, profile: ProfileSpec) -> GraphPlan:
        node_ids = set(profile.nodes)
        if profile.entry not in node_ids:
            raise ValidationError(
                "local_worker.graph_plan",
                f"Profile {profile.profile_id} entry is not in nodes",
                {"entry": profile.entry, "nodes": profile.nodes},
            )
        if len(node_ids) != len(profile.nodes):
            raise ValidationError(
                "local_worker.graph_plan",
                f"Profile {profile.profile_id} contains duplicate nodes",
                {"nodes": profile.nodes},
            )

        edges = self._compile_edges(profile, node_ids)
        reachable = self._reachable(profile.entry, edges)
        missing_reachability = sorted(node_ids - reachable)
        if missing_reachability:
            raise ValidationError(
                "local_worker.graph_plan",
                f"Profile {profile.profile_id} contains unreachable nodes",
                {"unreachable": missing_reachability},
            )

        outgoing = {edge.source for edge in edges}
        terminal_nodes = tuple(node for node in profile.nodes if node not in outgoing)
        if not terminal_nodes:
            raise ValidationError(
                "local_worker.graph_plan",
                f"Profile {profile.profile_id} has no terminal nodes",
            )

        nodes = tuple(
            GraphNode(
                node_id=node_id,
                role=self.agent_registry.get(node_id).role,
                model_policy=self.agent_registry.get(node_id).model_policy,
            )
            for node_id in profile.nodes
        )
        return GraphPlan(
            profile_id=profile.profile_id,
            entry=profile.entry,
            nodes=nodes,
            edges=edges,
            terminal_nodes=terminal_nodes,
        )

    def _compile_edges(self, profile: ProfileSpec, node_ids: set[str]) -> tuple[GraphEdge, ...]:
        raw_edges = profile.edges or self._linear_edges(profile.nodes)
        edges: list[GraphEdge] = []
        for edge in raw_edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValidationError(
                    "local_worker.graph_plan",
                    f"Profile {profile.profile_id} edge references unknown node",
                    {"edge": {"from": edge.source, "to": edge.target}},
                )
            edges.append(GraphEdge(edge.source, edge.target, edge.condition))
        return tuple(edges)

    def _linear_edges(self, nodes: tuple[str, ...]) -> tuple[ProfileEdge, ...]:
        return tuple(ProfileEdge(source=left, target=right) for left, right in zip(nodes, nodes[1:]))

    def _reachable(self, entry: str, edges: tuple[GraphEdge, ...]) -> set[str]:
        adjacency: dict[str, list[str]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source, []).append(edge.target)
        seen = {entry}
        stack = [entry]
        while stack:
            node = stack.pop()
            for target in adjacency.get(node, []):
                if target not in seen:
                    seen.add(target)
                    stack.append(target)
        return seen

