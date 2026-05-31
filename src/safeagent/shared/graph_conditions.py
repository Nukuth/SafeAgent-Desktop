from __future__ import annotations

from safeagent.shared.enums import RiskLevel

LOW = "low"
MEDIUM = "medium"
HIGH = "high"
MEDIUM_OR_HIGHER = "medium_or_higher"
APPROVED = "approved"
REVIEW_PASSED = "review_passed"

ALLOWED_EDGE_CONDITIONS = frozenset(
    {
        LOW,
        MEDIUM,
        HIGH,
        MEDIUM_OR_HIGHER,
        APPROVED,
        REVIEW_PASSED,
    }
)


def is_allowed_edge_condition(condition: str | None) -> bool:
    return condition is None or condition in ALLOWED_EDGE_CONDITIONS


def risk_condition_matches(condition: str, risk_level: RiskLevel) -> bool | None:
    if condition == LOW:
        return risk_level == RiskLevel.LOW
    if condition == MEDIUM:
        return risk_level == RiskLevel.MEDIUM
    if condition == HIGH:
        return risk_level in {RiskLevel.HIGH, RiskLevel.EXTREME}
    if condition == MEDIUM_OR_HIGHER:
        return risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.EXTREME}
    return None
