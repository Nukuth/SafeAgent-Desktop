from __future__ import annotations

from safeagent.shared.enums import RemotePermission
from safeagent.shared.enums import Severity
from safeagent.shared.errors import SafeAgentError, ValidationError


class RemotePermissionError(SafeAgentError):
    def __init__(self, message: str, details: dict[str, object]) -> None:
        super().__init__(
            "auth.failed",
            "shared.remote_permissions",
            message,
            severity=Severity.WARNING,
            retriable=False,
            details=details,
        )


def parse_remote_permission(value: str | RemotePermission | None) -> RemotePermission:
    if isinstance(value, RemotePermission):
        return value
    if value is None or not str(value).strip():
        return RemotePermission.SUBMIT_TASK
    try:
        return RemotePermission(str(value))
    except ValueError as exc:
        raise ValidationError(
            "shared.remote_permissions",
            f"Unsupported remote permission: {value}",
            {
                "permission": str(value),
                "allowed_permissions": [permission.value for permission in RemotePermission],
            },
        ) from exc


def require_submit_task_permission(permission: str | RemotePermission | None) -> RemotePermission:
    parsed = parse_remote_permission(permission)
    if parsed != RemotePermission.SUBMIT_TASK:
        raise RemotePermissionError(
            f"Remote permission {parsed.value} cannot submit tasks",
            {"required_permission": RemotePermission.SUBMIT_TASK.value, "actual_permission": parsed.value},
        )
    return parsed


def require_approval_permission(permission: str | RemotePermission | None) -> RemotePermission:
    parsed = parse_remote_permission(permission)
    if parsed not in {RemotePermission.APPROVAL_ONLY, RemotePermission.SUBMIT_TASK}:
        raise RemotePermissionError(
            f"Remote permission {parsed.value} cannot approve tasks",
            {
                "required_permission": [RemotePermission.APPROVAL_ONLY.value, RemotePermission.SUBMIT_TASK.value],
                "actual_permission": parsed.value,
            },
        )
    return parsed


def validate_task_remote_permission(permission: str | RemotePermission | None) -> RemotePermission:
    parsed = parse_remote_permission(permission)
    if parsed != RemotePermission.SUBMIT_TASK:
        raise ValidationError(
            "shared.remote_permissions",
            "New remote tasks must be created with submit_task permission",
            {"actual_permission": parsed.value, "required_permission": RemotePermission.SUBMIT_TASK.value},
        )
    return parsed
