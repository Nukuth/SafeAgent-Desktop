from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from safeagent.local_worker.config_sync import canonical_config, compare_config_pairs, load_json_config
from safeagent.local_worker.providers import load_model_provider_specs
from safeagent.local_worker.registry import load_default_registries
from safeagent.shared.enums import NetworkMode
from safeagent.shared.errors import SafeAgentError


@dataclass(frozen=True, slots=True)
class ConfigReviewFinding:
    severity: str
    code: str
    message: str
    path: str
    details: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "details": self.details,
        }


@dataclass(frozen=True, slots=True)
class ConfigReviewReport:
    config_dir: str
    config_hash: str
    findings: tuple[ConfigReviewFinding, ...]

    @property
    def blocking_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocking")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    def to_dict(self) -> dict[str, object]:
        return {
            "config_dir": self.config_dir,
            "config_hash": self.config_hash,
            "blocking_count": self.blocking_count,
            "warning_count": self.warning_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def review_config_directory(config_dir: Path) -> ConfigReviewReport:
    config_dir = config_dir.resolve()
    findings: list[ConfigReviewFinding] = []
    pairs = [
        (config_dir / "agents.yaml", config_dir / "agents.json"),
        (config_dir / "profiles.yaml", config_dir / "profiles.json"),
        (config_dir / "models.yaml", config_dir / "models.json"),
    ]
    try:
        mismatches = compare_config_pairs(pairs)
        if mismatches:
            for mismatch in mismatches:
                findings.append(
                    ConfigReviewFinding(
                        severity="blocking",
                        code="config.yaml_json_mismatch",
                        message="YAML and JSON config files must stay semantically identical",
                        path=mismatch["json"],
                        details={"yaml": mismatch["yaml"], "json": mismatch["json"]},
                    )
                )
        load_default_registries(config_dir)
        model_specs = load_model_provider_specs(config_dir / "models.json")
    except SafeAgentError as exc:
        findings.append(
            ConfigReviewFinding(
                severity="blocking",
                code="config.validation_failed",
                message=exc.envelope.message,
                path=str(config_dir),
                details={
                    "error_code": exc.envelope.code,
                    "module": exc.envelope.module,
                    **exc.envelope.details,
                },
            )
        )
        return ConfigReviewReport(str(config_dir), _config_hash(config_dir), tuple(findings))

    agents = load_json_config(config_dir / "agents.json")["agents"]
    profiles = load_json_config(config_dir / "profiles.json")["profiles"]
    findings.extend(_review_agent_permissions(config_dir / "agents.json", agents))
    findings.extend(_review_profile_permissions(config_dir / "profiles.json", profiles))
    findings.extend(_review_model_permissions(config_dir / "models.json", model_specs))
    return ConfigReviewReport(str(config_dir), _config_hash(config_dir), tuple(findings))


def _review_agent_permissions(path: Path, agents: dict[str, Any]) -> list[ConfigReviewFinding]:
    findings: list[ConfigReviewFinding] = []
    for agent_id, raw in agents.items():
        permissions = raw.get("permissions", {})
        network = raw.get("network", {})
        tools = set(raw.get("tools", []))
        if agent_id == "executor" and (permissions.get("can_execute") or permissions.get("can_write")):
            findings.append(
                ConfigReviewFinding(
                    severity="warning",
                    code="agent.executor_boundary",
                    message="executor is the only agent allowed to hold local execution/write permissions",
                    path=str(path),
                    details={
                        "agent_id": agent_id,
                        "can_execute": bool(permissions.get("can_execute")),
                        "can_write": bool(permissions.get("can_write")),
                        "tools": sorted(tools),
                        "required_controls": ["rule_reviewer", "human_approval", "policy_engine", "audit_log"],
                    },
                )
            )
        if network.get("allowed"):
            findings.append(
                ConfigReviewFinding(
                    severity="warning",
                    code="agent.network_enabled",
                    message="network-enabled agents are sensitive and must remain search-only unless explicitly upgraded",
                    path=str(path),
                    details={
                        "agent_id": agent_id,
                        "mode": network.get("mode"),
                        "can_download": bool(network.get("can_download")),
                    },
                )
            )
    return findings


def _review_profile_permissions(path: Path, profiles: dict[str, Any]) -> list[ConfigReviewFinding]:
    findings: list[ConfigReviewFinding] = []
    for profile_id, raw in profiles.items():
        nodes = set(raw.get("nodes", []))
        remote_allowed = bool(raw.get("remote_allowed", False))
        network_mode = str(raw.get("network_mode", NetworkMode.API_ONLY.value))
        if remote_allowed and "executor" in nodes:
            findings.append(
                ConfigReviewFinding(
                    severity="warning",
                    code="profile.remote_executor",
                    message="remote-allowed profiles that can reach executor require strict local approval gates",
                    path=str(path),
                    details={
                        "profile_id": profile_id,
                        "network_mode": network_mode,
                        "required_edges": [{"from": "human_approval", "to": "executor", "condition": "approved"}],
                    },
                )
            )
        if network_mode != NetworkMode.API_ONLY.value:
            findings.append(
                ConfigReviewFinding(
                    severity="warning",
                    code="profile.network_mode",
                    message="profile uses a non-default network mode",
                    path=str(path),
                    details={
                        "profile_id": profile_id,
                        "network_mode": network_mode,
                        "remote_allowed": remote_allowed,
                    },
                )
            )
    return findings


def _review_model_permissions(path: Path, model_specs: dict[str, Any]) -> list[ConfigReviewFinding]:
    findings: list[ConfigReviewFinding] = []
    for provider_id, spec in model_specs.items():
        if provider_id != "local_qwen" and spec.default_api_key:
            findings.append(
                ConfigReviewFinding(
                    severity="blocking",
                    code="model.default_api_key",
                    message="remote model providers must not use default API keys in config",
                    path=str(path),
                    details={"provider_id": provider_id, "api_key_env": spec.api_key_env},
                )
            )
        if provider_id == "codex" and not spec.enabled:
            findings.append(
                ConfigReviewFinding(
                    severity="warning",
                    code="model.codex_disabled",
                    message="Codex reviewer provider is disabled; high-risk review remains a placeholder route",
                    path=str(path),
                    details={"provider_id": provider_id, "api_key_env": spec.api_key_env},
                )
            )
        if provider_id == "local_qwen" and not _is_local_base_url(spec.base_url):
            findings.append(
                ConfigReviewFinding(
                    severity="warning",
                    code="model.local_qwen_remote_url",
                    message="local_qwen should normally point at a local OpenAI-compatible endpoint",
                    path=str(path),
                    details={"provider_id": provider_id, "base_url": spec.base_url},
                )
            )
    return findings


def _is_local_base_url(base_url: str) -> bool:
    lowered = base_url.lower()
    return lowered.startswith("http://127.0.0.1") or lowered.startswith("http://localhost")


def _config_hash(config_dir: Path) -> str:
    paths = [
        config_dir / "agents.json",
        config_dir / "profiles.json",
        config_dir / "models.json",
    ]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        try:
            payload = canonical_config(load_json_config(path))
            encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        except SafeAgentError:
            encoded = path.read_bytes() if path.exists() else b"<missing>"
        digest.update(encoded)
    return digest.hexdigest()
