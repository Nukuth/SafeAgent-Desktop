from __future__ import annotations

from collections import Counter
from typing import Any

from safeagent.shared.enums import EventType
from safeagent.shared.redaction import redact_payload


TERMINAL_STATUS_BY_EVENT = {
    EventType.RUN_COMPLETED.value: "completed",
    EventType.RUN_FAILED.value: "failed",
    EventType.EXECUTION_SKIPPED.value: "blocked_or_skipped",
    EventType.APPROVAL_REQUESTED.value: "waiting_approval",
}


def build_run_diagnostics(events: list[dict[str, Any]], approvals: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a stable, redacted run summary from stored events.

    The control-plane server must not understand worker internals. This helper
    only reads generic event fields and nested diagnostic keys that were already
    uploaded as redacted event details.
    """

    event_types = [str(event.get("event_type", "")) for event in events]
    agents = sorted({str(event.get("agent", "")) for event in events if event.get("agent")})
    risk_levels = [str(event.get("risk_level", "low")) for event in events]
    network_modes = [str(event.get("network_mode", "api_only")) for event in events]
    error_events = _error_events(events)
    blocking_events = _blocking_events(events)
    edge_summary = _edge_summary(events)
    diagnostic = {
        "event_count": len(events),
        "approval_count": len(approvals),
        "status": _infer_status(events),
        "last_event_type": event_types[-1] if event_types else None,
        "agents": agents,
        "risk_level": _highest_risk(risk_levels),
        "network_modes": sorted(set(network_modes)),
        "event_type_counts": dict(Counter(event_types)),
        "error_count": len(error_events),
        "errors": error_events,
        "blocking_reasons": blocking_events,
        "edge_decisions": edge_summary,
    }
    return redact_payload(diagnostic)


def _infer_status(events: list[dict[str, Any]]) -> str:
    for event in reversed(events):
        event_type = str(event.get("event_type", ""))
        if event_type in TERMINAL_STATUS_BY_EVENT:
            return TERMINAL_STATUS_BY_EVENT[event_type]
    if events:
        return "running_or_incomplete"
    return "not_found"


def _highest_risk(risk_levels: list[str]) -> str:
    order = {"low": 0, "medium": 1, "high": 2, "extreme": 3}
    highest = "low"
    for risk in risk_levels:
        if order.get(risk, 0) > order.get(highest, 0):
            highest = risk
    return highest


def _error_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for event in events:
        details = event.get("details", {})
        if not isinstance(details, dict):
            details = {}
        error = _extract_error(details)
        if error or event.get("event_type") == EventType.RUN_FAILED.value:
            errors.append(
                {
                    "event_id": event.get("event_id"),
                    "agent": event.get("agent"),
                    "event_type": event.get("event_type"),
                    "summary": event.get("summary"),
                    "error": error,
                }
            )
    return errors


def _blocking_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for event in events:
        if event.get("event_type") not in {
            EventType.EXECUTION_SKIPPED.value,
            EventType.APPROVAL_REQUESTED.value,
        }:
            continue
        details = event.get("details", {})
        if not isinstance(details, dict):
            details = {}
        reasons.append(
            {
                "agent": event.get("agent"),
                "event_type": event.get("event_type"),
                "summary": event.get("summary"),
                "reason": details.get("reason") or details.get("message") or event.get("summary"),
                "plan_hash": details.get("plan_hash"),
                "command_hash": details.get("command_hash"),
            }
        )
    return reasons


def _edge_summary(events: list[dict[str, Any]]) -> dict[str, int]:
    selected = 0
    skipped = 0
    failed = 0
    for event in events:
        details = event.get("details", {})
        if not isinstance(details, dict):
            continue
        for decision in details.get("edge_decisions", []) or []:
            if not isinstance(decision, dict):
                continue
            if decision.get("selected") is True:
                selected += 1
            else:
                skipped += 1
                if "Unknown graph edge condition" in str(decision.get("reason", "")):
                    failed += 1
    return {
        "selected": selected,
        "skipped": skipped,
        "failed": failed,
    }


def _extract_error(details: dict[str, Any]) -> dict[str, Any] | None:
    direct = details.get("error")
    if isinstance(direct, dict):
        return direct
    validation = details.get("validation")
    if isinstance(validation, dict) and validation.get("error"):
        error = validation.get("error")
        return error if isinstance(error, dict) else {"message": str(error)}
    node_results = details.get("node_results")
    if isinstance(node_results, list):
        for node in node_results:
            if isinstance(node, dict) and isinstance(node.get("error"), dict):
                return node["error"]
    return None
