from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from safeagent.shared.enums import EventType, NetworkMode, RemotePermission, RiskLevel, TaskStatus
from safeagent.shared.ids import new_id
from safeagent.shared.time import utc_now_iso


@dataclass(slots=True)
class TaskCreate:
    content: str
    device_id: str
    requested_profile: str | None = None
    remote_permission: RemotePermission = RemotePermission.SUBMIT_TASK


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    device_id: str
    content: str
    status: TaskStatus
    source: Literal["local", "remote"] = "remote"
    requested_profile: str | None = None
    remote_permission: RemotePermission = RemotePermission.SUBMIT_TASK
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    @classmethod
    def create(cls, task: TaskCreate) -> "TaskRecord":
        return cls(
            task_id=new_id("task"),
            device_id=task.device_id,
            content=task.content,
            status=TaskStatus.PENDING,
            requested_profile=task.requested_profile,
            remote_permission=task.remote_permission,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["remote_permission"] = self.remote_permission.value
        return data


@dataclass(slots=True)
class RunEvent:
    task_id: str
    run_id: str
    agent: str
    event_type: EventType
    summary: str
    risk_level: RiskLevel = RiskLevel.LOW
    network_mode: NetworkMode = NetworkMode.API_ONLY
    redacted: bool = True
    details: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("evt"))
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["risk_level"] = self.risk_level.value
        data["network_mode"] = self.network_mode.value
        return data


@dataclass(slots=True)
class ApprovalRecord:
    task_id: str
    run_id: str
    decision: Literal["approved", "rejected"]
    approved_by: str
    approval_scope: Literal["plan_only", "task"] = "plan_only"
    plan_hash: str | None = None
    expires_at: str | None = None
    approval_id: str = field(default_factory=lambda: new_id("approval"))
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

