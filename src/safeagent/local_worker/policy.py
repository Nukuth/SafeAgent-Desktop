from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from safeagent.shared.enums import NetworkMode, RiskLevel


SYSTEM_PATH_MARKERS = (
    r"c:\windows",
    r"c:\program files",
    r"c:\program files (x86)",
    r"\appdata\roaming\microsoft\windows\start menu",
)

HIGH_RISK_PATTERNS = (
    r"\bdiskpart\b",
    r"\bformat\b",
    r"\bbcdedit\b",
    r"\bbootrec\b",
    r"\breg\s+(add|delete|import)\b",
    r"\bfastboot\s+(flash|erase)\b",
    r"\badb\s+shell\s+rm\b",
    r"\badb\s+sideload\b",
)

MEDIUM_RISK_PATTERNS = (
    r"\bremove-item\b",
    r"\bdel\b",
    r"\brmdir\b",
    r"\bmove-item\b",
    r"\bcopy-item\b",
    r"\bsetx\b",
    r"\binstall\b",
    r"\binvoke-webrequest\b",
    r"\bcurl\b",
)


@dataclass(slots=True)
class PolicyDecision:
    allowed: bool
    risk_level: RiskLevel
    requires_local_confirmation: bool
    reasons: list[str] = field(default_factory=list)
    safe_alternative: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "risk_level": self.risk_level.value,
            "requires_local_confirmation": self.requires_local_confirmation,
            "reasons": self.reasons,
            "safe_alternative": self.safe_alternative,
        }


class PolicyEngine:
    """Deterministic local safety policy.

    This engine intentionally does not call models. It is the first safety gate
    for remote tasks and generated command proposals.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.downloads_dir = (self.workspace_root / "downloads").resolve()

    def evaluate_task(self, content: str, network_mode: NetworkMode = NetworkMode.API_ONLY) -> PolicyDecision:
        text = content.lower()
        reasons: list[str] = []
        risk = RiskLevel.LOW

        if network_mode == NetworkMode.LOCKDOWN:
            return PolicyDecision(
                allowed=False,
                risk_level=RiskLevel.EXTREME,
                requires_local_confirmation=True,
                reasons=["lockdown mode blocks all remote task execution"],
            )

        if any(re.search(pattern, text, re.I) for pattern in HIGH_RISK_PATTERNS):
            risk = RiskLevel.HIGH
            reasons.append("task contains high-risk system, adb, fastboot, registry, boot, or disk operation")

        if any(re.search(pattern, text, re.I) for pattern in MEDIUM_RISK_PATTERNS):
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
            reasons.append("task appears to involve file mutation, install, download, or shell-side effects")

        if "下载" in text or "download" in text:
            if network_mode not in {NetworkMode.DOWNLOAD_GUARDED, NetworkMode.SEARCH_ALLOWED}:
                risk = max_risk(risk, RiskLevel.MEDIUM)
                reasons.append("download intent requires guarded network mode")

        if "删除" in text or "delete" in text or "remove" in text:
            risk = max_risk(risk, RiskLevel.HIGH)
            reasons.append("delete intent requires local confirmation")

        if self._mentions_system_path(text):
            risk = max_risk(risk, RiskLevel.HIGH)
            reasons.append("task mentions system-sensitive path")

        if risk in {RiskLevel.HIGH, RiskLevel.EXTREME}:
            return PolicyDecision(
                allowed=False,
                risk_level=risk,
                requires_local_confirmation=True,
                reasons=reasons,
                safe_alternative="Generate a plan and request local confirmation before execution.",
            )

        return PolicyDecision(
            allowed=True,
            risk_level=risk,
            requires_local_confirmation=(risk == RiskLevel.MEDIUM),
            reasons=reasons or ["no risky pattern detected by local policy"],
        )

    def assert_download_target(self, target: Path) -> PolicyDecision:
        resolved = target.resolve()
        if not is_relative_to(resolved, self.downloads_dir):
            return PolicyDecision(
                allowed=False,
                risk_level=RiskLevel.HIGH,
                requires_local_confirmation=True,
                reasons=[f"download target must stay under {self.downloads_dir}"],
            )
        return PolicyDecision(
            allowed=True,
            risk_level=RiskLevel.MEDIUM,
            requires_local_confirmation=True,
            reasons=["download target is inside guarded downloads directory"],
        )

    def _mentions_system_path(self, text: str) -> bool:
        normalized = text.replace("/", "\\")
        return any(marker in normalized for marker in SYSTEM_PATH_MARKERS)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    order = {
        RiskLevel.LOW: 0,
        RiskLevel.MEDIUM: 1,
        RiskLevel.HIGH: 2,
        RiskLevel.EXTREME: 3,
    }
    return left if order[left] >= order[right] else right

