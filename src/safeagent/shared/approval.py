from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ApprovalCheck:
    valid: bool
    reason: str


def check_approval(
    *,
    decision: str | None,
    approval_plan_hash: str | None,
    expected_plan_hash: str,
    expires_at: str | None,
    now: datetime | None = None,
) -> ApprovalCheck:
    if decision != "approved":
        return ApprovalCheck(False, "approval decision is not approved")
    if approval_plan_hash != expected_plan_hash:
        return ApprovalCheck(False, "approval plan_hash does not match current plan")
    if not expires_at:
        return ApprovalCheck(False, "approval has no expires_at")
    now = now or datetime.now(UTC)
    try:
        expires = datetime.fromisoformat(expires_at)
    except ValueError:
        return ApprovalCheck(False, "approval expires_at is not a valid ISO datetime")
    if expires.tzinfo is None:
        return ApprovalCheck(False, "approval expires_at must include timezone")
    if expires <= now:
        return ApprovalCheck(False, "approval has expired")
    return ApprovalCheck(True, "approval is valid for current plan")

