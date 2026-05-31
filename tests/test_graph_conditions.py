from safeagent.shared.enums import RiskLevel
from safeagent.shared.graph_conditions import (
    ALLOWED_EDGE_CONDITIONS,
    APPROVED,
    HIGH,
    LOW,
    MEDIUM,
    MEDIUM_OR_HIGHER,
    REVIEW_PASSED,
    is_allowed_edge_condition,
    risk_condition_matches,
)


def test_allowed_edge_conditions_are_explicit():
    assert ALLOWED_EDGE_CONDITIONS == {
        LOW,
        MEDIUM,
        HIGH,
        MEDIUM_OR_HIGHER,
        APPROVED,
        REVIEW_PASSED,
    }
    assert is_allowed_edge_condition(None) is True
    assert is_allowed_edge_condition("maybe") is False


def test_risk_condition_matches_supported_risk_conditions():
    assert risk_condition_matches(LOW, RiskLevel.LOW) is True
    assert risk_condition_matches(LOW, RiskLevel.MEDIUM) is False
    assert risk_condition_matches(MEDIUM, RiskLevel.MEDIUM) is True
    assert risk_condition_matches(HIGH, RiskLevel.HIGH) is True
    assert risk_condition_matches(HIGH, RiskLevel.EXTREME) is True
    assert risk_condition_matches(MEDIUM_OR_HIGHER, RiskLevel.LOW) is False
    assert risk_condition_matches(MEDIUM_OR_HIGHER, RiskLevel.MEDIUM) is True
    assert risk_condition_matches(APPROVED, RiskLevel.LOW) is None
