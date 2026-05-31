import json
from pathlib import Path

from safeagent.local_worker.registry import AgentRegistry, ProfileRegistry, load_default_registries
from safeagent.shared.errors import ValidationError


def write_json(path: Path, payload: dict):
    path.write_text(json.dumps(payload), encoding="utf-8")


def minimal_agents_payload(extra_agents: dict | None = None) -> dict:
    agents = {
        "planner": {
            "role": "thinker",
            "model_policy": "deepseek_default",
            "tools": [],
            "permissions": {"can_execute": False, "can_write": False},
            "network": {"allowed": False},
        },
        "rule_reviewer": {
            "role": "reviewer",
            "model_policy": "none",
            "tools": [],
            "permissions": {"can_execute": False, "can_write": False},
            "network": {"allowed": False},
        },
        "human_approval": {
            "role": "reviewer",
            "model_policy": "none",
            "tools": [],
            "permissions": {"can_execute": False, "can_write": False},
            "network": {"allowed": False},
        },
        "executor": {
            "role": "actor",
            "model_policy": "none",
            "tools": ["local_executor"],
            "permissions": {"can_execute": True, "can_write": True},
            "network": {"allowed": False},
        },
        "search_agent": {
            "role": "producer",
            "model_policy": "deepseek_default",
            "tools": ["web_search"],
            "permissions": {"can_execute": False, "can_write": False},
            "network": {"allowed": True, "mode": "search_only", "can_download": False},
        },
    }
    if extra_agents:
        agents.update(extra_agents)
    return {"agents": agents}


def test_default_registries_load_and_validate():
    agents, profiles = load_default_registries(Path("configs"))
    assert agents.has("planner")
    assert agents.has("executor")
    assert profiles.get("research").network_mode.value == "search_allowed"


def test_profile_rejects_unknown_agent(tmp_path):
    agents_path = tmp_path / "agents.json"
    profiles_path = tmp_path / "profiles.json"
    write_json(
        agents_path,
        {
            "agents": {
                "planner": {
                    "role": "thinker",
                    "model_policy": "deepseek_default",
                    "tools": [],
                    "permissions": {"can_execute": False, "can_write": False},
                    "network": {"allowed": False},
                }
            }
        },
    )
    write_json(
        profiles_path,
        {
            "profiles": {
                "bad": {
                    "network_mode": "api_only",
                    "remote_allowed": True,
                    "nodes": ["planner", "missing_agent"],
                }
            }
        },
    )
    registry = AgentRegistry.from_file(agents_path)
    try:
        ProfileRegistry.from_file(profiles_path, registry)
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert "missing_agent" in str(exc.envelope.details)
    else:
        raise AssertionError("expected ValidationError")


def test_agent_contract_rejects_non_executor_execute_permission(tmp_path):
    agents_path = tmp_path / "agents.json"
    write_json(
        agents_path,
        minimal_agents_payload(
            {
                "shell_agent": {
                    "role": "producer",
                    "model_policy": "deepseek_default",
                    "tools": [],
                    "permissions": {"can_execute": True, "can_write": False},
                    "network": {"allowed": False},
                }
            }
        ),
    )
    try:
        AgentRegistry.from_file(agents_path)
    except ValidationError as exc:
        assert "Only executor" in exc.envelope.message
        assert exc.envelope.details["agent_id"] == "shell_agent"
    else:
        raise AssertionError("expected ValidationError")


def test_agent_contract_rejects_search_download_permission(tmp_path):
    agents_path = tmp_path / "agents.json"
    payload = minimal_agents_payload()
    payload["agents"]["search_agent"]["network"]["can_download"] = True
    write_json(agents_path, payload)
    try:
        AgentRegistry.from_file(agents_path)
    except ValidationError as exc:
        assert "without downloads" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")


def test_profile_contract_requires_approval_edge_before_executor(tmp_path):
    agents_path = tmp_path / "agents.json"
    profiles_path = tmp_path / "profiles.json"
    write_json(agents_path, minimal_agents_payload())
    write_json(
        profiles_path,
        {
            "profiles": {
                "bad_executor": {
                    "network_mode": "api_only",
                    "remote_allowed": True,
                    "entry": "planner",
                    "nodes": ["planner", "rule_reviewer", "human_approval", "executor"],
                    "edges": [
                        {"from": "planner", "to": "rule_reviewer"},
                        {"from": "rule_reviewer", "to": "executor", "condition": "low"},
                    ],
                }
            }
        },
    )
    registry = AgentRegistry.from_file(agents_path)
    try:
        ProfileRegistry.from_file(profiles_path, registry)
    except ValidationError as exc:
        assert "approved human_approval edge" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")


def test_profile_contract_rejects_network_agent_in_api_only_profile(tmp_path):
    agents_path = tmp_path / "agents.json"
    profiles_path = tmp_path / "profiles.json"
    write_json(agents_path, minimal_agents_payload())
    write_json(
        profiles_path,
        {
            "profiles": {
                "bad_network": {
                    "network_mode": "api_only",
                    "remote_allowed": True,
                    "entry": "planner",
                    "nodes": ["planner", "search_agent"],
                    "edges": [{"from": "planner", "to": "search_agent"}],
                }
            }
        },
    )
    registry = AgentRegistry.from_file(agents_path)
    try:
        ProfileRegistry.from_file(profiles_path, registry)
    except ValidationError as exc:
        assert "network-enabled agents" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")


def test_profile_contract_rejects_unknown_edge_condition(tmp_path):
    agents_path = tmp_path / "agents.json"
    profiles_path = tmp_path / "profiles.json"
    write_json(agents_path, minimal_agents_payload())
    write_json(
        profiles_path,
        {
            "profiles": {
                "bad_condition": {
                    "network_mode": "api_only",
                    "remote_allowed": True,
                    "entry": "planner",
                    "nodes": ["planner", "rule_reviewer", "human_approval", "executor"],
                    "edges": [
                        {"from": "planner", "to": "rule_reviewer"},
                        {"from": "rule_reviewer", "to": "human_approval", "condition": "maybe"},
                        {"from": "human_approval", "to": "executor", "condition": "approved"},
                    ],
                }
            }
        },
    )
    registry = AgentRegistry.from_file(agents_path)
    try:
        ProfileRegistry.from_file(profiles_path, registry)
    except ValidationError as exc:
        assert "unsupported edge condition" in exc.envelope.message
        assert exc.envelope.details["invalid_conditions"] == ["maybe"]
        assert "approved" in exc.envelope.details["allowed_conditions"]
    else:
        raise AssertionError("expected ValidationError")
