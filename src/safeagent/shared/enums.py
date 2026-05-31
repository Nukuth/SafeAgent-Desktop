from __future__ import annotations

from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class NetworkMode(StrEnum):
    OFFLINE = "offline"
    API_ONLY = "api_only"
    SEARCH_ALLOWED = "search_allowed"
    DOWNLOAD_GUARDED = "download_guarded"
    REMOTE_CONTROL = "remote_control"
    LOCKDOWN = "lockdown"


class TaskStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    REJECTED = "rejected"


class EventType(StrEnum):
    TASK_CREATED = "task_created"
    TASK_CLAIMED = "task_claimed"
    HEARTBEAT = "heartbeat"
    GRAPH_RUN_STARTED = "graph_run_started"
    GRAPH_NODE_COMPLETED = "graph_node_completed"
    GRAPH_NODE_FAILED = "graph_node_failed"
    GRAPH_RUN_COMPLETED = "graph_run_completed"
    PROFILE_SELECTED = "profile_selected"
    MODEL_ROUTE_SELECTED = "model_route_selected"
    RISK_DETECTED = "risk_detected"
    POLICY_DECISION = "policy_decision"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECORDED = "approval_recorded"
    COMMAND_PROPOSED = "command_proposed"
    COMMAND_VALIDATED = "command_validated"
    EXECUTION_SKIPPED = "execution_skipped"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class RemotePermission(StrEnum):
    VIEW_ONLY = "view_only"
    APPROVAL_ONLY = "approval_only"
    SUBMIT_TASK = "submit_task"
