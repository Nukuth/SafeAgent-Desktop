from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from safeagent.shared.enums import NetworkMode
from safeagent.shared.errors import ValidationError
from safeagent.shared.graph_conditions import ALLOWED_EDGE_CONDITIONS, is_allowed_edge_condition


@dataclass(frozen=True, slots=True)
class AgentPermissions:
    can_execute: bool
    can_write: bool


@dataclass(frozen=True, slots=True)
class AgentNetworkPolicy:
    allowed: bool
    mode: str | None = None
    can_download: bool = False


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    role: str
    model_policy: str
    tools: tuple[str, ...]
    permissions: AgentPermissions
    network: AgentNetworkPolicy


@dataclass(frozen=True, slots=True)
class ProfileSpec:
    profile_id: str
    network_mode: NetworkMode
    remote_allowed: bool
    nodes: tuple[str, ...]
    entry: str
    edges: tuple["ProfileEdge", ...]


@dataclass(frozen=True, slots=True)
class ProfileEdge:
    source: str
    target: str
    condition: str | None = None


class AgentRegistry:
    def __init__(self, agents: dict[str, AgentSpec]) -> None:
        self._agents = agents
        self._validate_agent_security_contracts()

    @classmethod
    def from_file(cls, path: Path) -> "AgentRegistry":
        data = load_json_object(path, "agents")
        agents: dict[str, AgentSpec] = {}
        for agent_id, raw in data["agents"].items():
            try:
                permissions = AgentPermissions(
                    can_execute=bool(raw["permissions"]["can_execute"]),
                    can_write=bool(raw["permissions"]["can_write"]),
                )
                network_raw = raw.get("network", {})
                network = AgentNetworkPolicy(
                    allowed=bool(network_raw.get("allowed", False)),
                    mode=network_raw.get("mode"),
                    can_download=bool(network_raw.get("can_download", False)),
                )
                agents[agent_id] = AgentSpec(
                    agent_id=agent_id,
                    role=str(raw["role"]),
                    model_policy=str(raw["model_policy"]),
                    tools=tuple(str(tool) for tool in raw.get("tools", [])),
                    permissions=permissions,
                    network=network,
                )
            except KeyError as exc:
                raise ValidationError(
                    "local_worker.registry",
                    f"Agent {agent_id} is missing required field {exc}",
                    {"path": str(path)},
                ) from exc
        return cls(agents)

    def get(self, agent_id: str) -> AgentSpec:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise ValidationError(
                "local_worker.registry",
                f"Unknown agent: {agent_id}",
                {"agent_id": agent_id},
            ) from exc

    def has(self, agent_id: str) -> bool:
        return agent_id in self._agents

    @property
    def ids(self) -> set[str]:
        return set(self._agents)

    def _validate_agent_security_contracts(self) -> None:
        for agent in self._agents.values():
            if (agent.permissions.can_execute or agent.permissions.can_write) and agent.agent_id != "executor":
                raise ValidationError(
                    "local_worker.registry",
                    "Only executor may have execute or write permissions",
                    {
                        "agent_id": agent.agent_id,
                        "can_execute": agent.permissions.can_execute,
                        "can_write": agent.permissions.can_write,
                    },
                )
            if "local_executor" in agent.tools and agent.agent_id != "executor":
                raise ValidationError(
                    "local_worker.registry",
                    "local_executor tool is reserved for executor",
                    {"agent_id": agent.agent_id},
                )
            if agent.network.allowed:
                if agent.agent_id != "search_agent":
                    raise ValidationError(
                        "local_worker.registry",
                        "Only search_agent may have network access by default",
                        {"agent_id": agent.agent_id},
                    )
                if agent.network.mode != "search_only" or agent.network.can_download:
                    raise ValidationError(
                        "local_worker.registry",
                        "search_agent network access must be search_only without downloads",
                        {
                            "agent_id": agent.agent_id,
                            "mode": agent.network.mode,
                            "can_download": agent.network.can_download,
                        },
                    )
            if agent.model_policy == "codex_review" and agent.agent_id != "codex_reviewer":
                raise ValidationError(
                    "local_worker.registry",
                    "codex_review model policy is reserved for codex_reviewer",
                    {"agent_id": agent.agent_id},
                )
            if agent.agent_id == "human_approval" and agent.model_policy != "none":
                raise ValidationError(
                    "local_worker.registry",
                    "human_approval cannot call a model",
                    {"agent_id": agent.agent_id, "model_policy": agent.model_policy},
                )


class ProfileRegistry:
    def __init__(self, profiles: dict[str, ProfileSpec], agent_registry: AgentRegistry) -> None:
        self._profiles = profiles
        self._agent_registry = agent_registry
        self._validate_profiles()

    @classmethod
    def from_file(cls, path: Path, agent_registry: AgentRegistry) -> "ProfileRegistry":
        data = load_json_object(path, "profiles")
        profiles: dict[str, ProfileSpec] = {}
        for profile_id, raw in data["profiles"].items():
            try:
                network_mode = NetworkMode(str(raw["network_mode"]))
                profiles[profile_id] = ProfileSpec(
                    profile_id=profile_id,
                    network_mode=network_mode,
                    remote_allowed=bool(raw["remote_allowed"]),
                    nodes=tuple(str(node) for node in raw["nodes"]),
                    entry=str(raw.get("entry", raw["nodes"][0])),
                    edges=tuple(
                        ProfileEdge(
                            source=str(edge["from"]),
                            target=str(edge["to"]),
                            condition=str(edge["condition"]) if "condition" in edge else None,
                        )
                        for edge in raw.get("edges", [])
                    ),
                )
            except (KeyError, ValueError) as exc:
                raise ValidationError(
                    "local_worker.registry",
                    f"Profile {profile_id} is invalid: {exc}",
                    {"path": str(path)},
                ) from exc
        return cls(profiles, agent_registry)

    def get(self, profile_id: str) -> ProfileSpec:
        try:
            return self._profiles[profile_id]
        except KeyError as exc:
            raise ValidationError(
                "local_worker.registry",
                f"Unknown profile: {profile_id}",
                {"profile_id": profile_id},
            ) from exc

    def has(self, profile_id: str) -> bool:
        return profile_id in self._profiles

    def _validate_profiles(self) -> None:
        for profile in self._profiles.values():
            missing = [node for node in profile.nodes if not self._agent_registry.has(node)]
            if missing:
                raise ValidationError(
                    "local_worker.registry",
                    f"Profile {profile.profile_id} references unknown agents",
                    {"missing_agents": missing},
                )
            self._validate_profile_security_contract(profile)

    def _validate_profile_security_contract(self, profile: ProfileSpec) -> None:
        nodes = set(profile.nodes)
        invalid_conditions = [
            edge.condition
            for edge in profile.edges
            if not is_allowed_edge_condition(edge.condition)
        ]
        if invalid_conditions:
            raise ValidationError(
                "local_worker.registry",
                "Profile contains unsupported edge condition",
                {
                    "profile_id": profile.profile_id,
                    "invalid_conditions": sorted(set(str(condition) for condition in invalid_conditions)),
                    "allowed_conditions": sorted(ALLOWED_EDGE_CONDITIONS),
                },
            )
        if "executor" in nodes:
            required = {"rule_reviewer", "human_approval"}
            missing_required = sorted(required - nodes)
            if missing_required:
                raise ValidationError(
                    "local_worker.registry",
                    "Profiles with executor must include rule_reviewer and human_approval",
                    {"profile_id": profile.profile_id, "missing_agents": missing_required},
                )
            approval_edges = [
                edge
                for edge in profile.edges
                if edge.source == "human_approval" and edge.target == "executor" and edge.condition == "approved"
            ]
            if not approval_edges:
                raise ValidationError(
                    "local_worker.registry",
                    "Profiles with executor must include approved human_approval edge",
                    {"profile_id": profile.profile_id},
                )
            unsafe_executor_edges = [
                edge
                for edge in profile.edges
                if edge.target == "executor" and edge.source not in {"rule_reviewer", "human_approval"}
            ]
            if unsafe_executor_edges:
                raise ValidationError(
                    "local_worker.registry",
                    "Executor may only be reached from rule_reviewer or human_approval",
                    {
                        "profile_id": profile.profile_id,
                        "edges": [
                            {"from": edge.source, "to": edge.target, "condition": edge.condition}
                            for edge in unsafe_executor_edges
                        ],
                    },
                )
        if "codex_reviewer" in nodes and not {"rule_reviewer", "human_approval"}.issubset(nodes):
            raise ValidationError(
                "local_worker.registry",
                "Profiles with codex_reviewer must include rule_reviewer and human_approval",
                {"profile_id": profile.profile_id},
            )
        network_agents = [
            node for node in profile.nodes if self._agent_registry.get(node).network.allowed
        ]
        if network_agents and profile.network_mode != NetworkMode.SEARCH_ALLOWED:
            raise ValidationError(
                "local_worker.registry",
                "Profiles containing network-enabled agents must use search_allowed network mode",
                {"profile_id": profile.profile_id, "network_agents": network_agents},
            )
        if profile.network_mode == NetworkMode.SEARCH_ALLOWED and "search_agent" not in nodes:
            raise ValidationError(
                "local_worker.registry",
                "search_allowed profiles must include search_agent",
                {"profile_id": profile.profile_id},
            )


def load_default_registries(config_dir: Path) -> tuple[AgentRegistry, ProfileRegistry]:
    agent_registry = AgentRegistry.from_file(config_dir / "agents.json")
    profile_registry = ProfileRegistry.from_file(config_dir / "profiles.json", agent_registry)
    return agent_registry, profile_registry


def load_json_object(path: Path, root_key: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(
            "local_worker.registry",
            f"Config file not found: {path}",
            {"path": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "local_worker.registry",
            f"Config file is not valid JSON: {path}",
            {"path": str(path), "error": str(exc)},
        ) from exc
    if not isinstance(data, dict) or root_key not in data:
        raise ValidationError(
            "local_worker.registry",
            f"Config file must contain top-level key {root_key}",
            {"path": str(path)},
        )
    return data
