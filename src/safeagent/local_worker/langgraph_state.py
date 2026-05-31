from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_node_outputs(
    current: dict[str, dict[str, Any]],
    update: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = dict(current)
    merged.update(update)
    return merged


class SafeAgentState(TypedDict, total=False):
    """LangGraph state contract for the local worker.

    This state intentionally carries data only. Nodes must return partial
    updates, and any real side effect still has to pass through PolicyEngine,
    approval validation, and Executor boundaries outside this schema.
    """

    task_id: str
    run_id: str
    profile_id: str
    payload: dict[str, Any]
    node_results: Annotated[list[dict[str, Any]], operator.add]
    edge_decisions: Annotated[list[dict[str, Any]], operator.add]
    node_outputs: Annotated[dict[str, dict[str, Any]], merge_node_outputs]
    status: str
    error: dict[str, Any] | None


def initial_langgraph_state(
    *,
    task_id: str,
    run_id: str,
    profile_id: str,
    payload: dict[str, Any] | None = None,
) -> SafeAgentState:
    return {
        "task_id": task_id,
        "run_id": run_id,
        "profile_id": profile_id,
        "payload": payload or {},
        "node_results": [],
        "edge_decisions": [],
        "node_outputs": {},
        "status": "created",
        "error": None,
    }
