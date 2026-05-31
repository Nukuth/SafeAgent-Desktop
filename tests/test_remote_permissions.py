from safeagent.shared.enums import RemotePermission
from safeagent.shared.errors import SafeAgentError, ValidationError
from safeagent.shared.remote_permissions import (
    parse_remote_permission,
    require_approval_permission,
    require_submit_task_permission,
    validate_task_remote_permission,
)


def test_remote_permission_defaults_to_submit_task_for_compatibility():
    assert parse_remote_permission(None) == RemotePermission.SUBMIT_TASK
    assert parse_remote_permission("") == RemotePermission.SUBMIT_TASK


def test_remote_permission_rejects_unknown_value():
    try:
        parse_remote_permission("admin")
    except ValidationError as exc:
        assert "Unsupported remote permission" in exc.envelope.message
        assert "admin" == exc.envelope.details["permission"]
    else:
        raise AssertionError("expected ValidationError")


def test_submit_task_permission_is_required_for_task_creation():
    assert require_submit_task_permission("submit_task") == RemotePermission.SUBMIT_TASK
    for permission in ("view_only", "approval_only"):
        try:
            require_submit_task_permission(permission)
        except SafeAgentError as exc:
            assert exc.envelope.code == "auth.failed"
            assert exc.envelope.details["actual_permission"] == permission
        else:
            raise AssertionError("expected AuthError")


def test_approval_permission_allows_approval_only_and_submit_task():
    assert require_approval_permission("approval_only") == RemotePermission.APPROVAL_ONLY
    assert require_approval_permission("submit_task") == RemotePermission.SUBMIT_TASK
    try:
        require_approval_permission("view_only")
    except SafeAgentError as exc:
        assert exc.envelope.details["actual_permission"] == "view_only"
    else:
        raise AssertionError("expected AuthError")


def test_new_remote_tasks_must_be_submit_task_permission():
    assert validate_task_remote_permission("submit_task") == RemotePermission.SUBMIT_TASK
    try:
        validate_task_remote_permission("approval_only")
    except ValidationError as exc:
        assert "submit_task permission" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")
