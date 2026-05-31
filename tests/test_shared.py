from pathlib import Path

from safeagent.shared.audit_log import JsonlAuditLog
from safeagent.shared.auth import require_bearer_token
from safeagent.shared.errors import AuthError
from safeagent.shared.redaction import redact_payload
from safeagent.shared.schemas import TaskCreate, TaskRecord


def test_auth_accepts_exact_bearer_token():
    require_bearer_token("Bearer secret-token", "secret-token")


def test_auth_rejects_missing_token():
    try:
        require_bearer_token(None, "secret-token")
    except AuthError as exc:
        assert exc.envelope.code == "auth.failed"
    else:
        raise AssertionError("expected AuthError")


def test_task_ids_are_uuid_prefixed():
    task = TaskRecord.create(TaskCreate(content="hello", device_id="pc"))
    assert task.task_id.startswith("task_")
    assert task.status.value == "pending"


def test_redaction_masks_secret_keys_and_values():
    redacted = redact_payload({"api_key": "sk-abc123456789XYZ", "note": "Bearer abcdefghijklmnop"})
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["note"] == "[REDACTED]"


def test_redaction_preserves_safe_audit_identifiers():
    payload = {
        "task_id": "task_1234567890abcdef1234567890abcdef",
        "run_id": "run_1234567890abcdef1234567890abcdef",
        "approval_id": "approval_1234567890abcdef1234567890abcdef",
        "plan_hash": "a" * 64,
        "api_key": "sk-abc123456789XYZ",
    }
    redacted = redact_payload(payload)
    assert redacted["task_id"] == payload["task_id"]
    assert redacted["run_id"] == payload["run_id"]
    assert redacted["approval_id"] == payload["approval_id"]
    assert redacted["plan_hash"] == payload["plan_hash"]
    assert redacted["api_key"] == "[REDACTED]"


def test_jsonl_audit_log_redacts(tmp_path: Path):
    path = tmp_path / "audit.jsonl"
    log = JsonlAuditLog(path)
    log.write({"token": "secret", "message": "ok"})
    text = path.read_text(encoding="utf-8")
    assert "[REDACTED]" in text
    assert "secret" not in text
