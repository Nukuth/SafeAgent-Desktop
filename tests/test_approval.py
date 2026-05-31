from datetime import UTC, datetime, timedelta

from safeagent.shared.approval import check_approval
from safeagent.shared.plan_hash import compute_plan_hash


def test_plan_hash_is_stable_for_key_order():
    left = compute_plan_hash({"b": 2, "a": 1})
    right = compute_plan_hash({"a": 1, "b": 2})
    assert left == right


def test_approval_requires_approved_decision():
    result = check_approval(
        decision="rejected",
        approval_plan_hash="abc",
        expected_plan_hash="abc",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    assert result.valid is False
    assert "not approved" in result.reason


def test_approval_requires_matching_plan_hash():
    result = check_approval(
        decision="approved",
        approval_plan_hash="old",
        expected_plan_hash="new",
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    assert result.valid is False
    assert "plan_hash" in result.reason


def test_approval_rejects_expired_timestamp():
    result = check_approval(
        decision="approved",
        approval_plan_hash="abc",
        expected_plan_hash="abc",
        expires_at=(datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
    )
    assert result.valid is False
    assert "expired" in result.reason

