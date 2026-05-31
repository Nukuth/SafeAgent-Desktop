import json
import sqlite3

from safeagent.server.db import TaskStore
from safeagent.shared.enums import EventType, TaskStatus
from safeagent.shared.errors import ValidationError
from safeagent.shared.schemas import ApprovalRecord, RunEvent, TaskCreate


def test_task_store_create_claim_event_and_approval(tmp_path):
    store = TaskStore(tmp_path / "server.sqlite3")

    task = store.create_task(TaskCreate(content="查看状态", device_id="pc-1"))
    assert task.status == TaskStatus.PENDING

    claimed = store.claim_pending("pc-1")
    assert len(claimed) == 1
    assert claimed[0]["task_id"] == task.task_id

    assert store.claim_pending("pc-1") == []

    event = RunEvent(
        task_id=task.task_id,
        run_id="run_1",
        agent="tester",
        event_type=EventType.RUN_COMPLETED,
        summary="done",
    )
    store.append_event(event)
    approval = ApprovalRecord(
        task_id=task.task_id,
        run_id="run_1",
        decision="approved",
        approved_by="user",
    )
    store.record_approval(approval)

    run = store.get_run("run_1")
    assert run["events"][0]["summary"] == "done"
    assert run["approvals"][0]["decision"] == "approved"
    assert run["diagnostics"]["status"] == "completed"
    assert run["diagnostics"]["event_count"] == 1
    assert run["diagnostics"]["approval_count"] == 1
    latest = store.latest_approval(task.task_id, "run_1")
    assert latest is not None
    assert latest["approval_id"] == approval.approval_id
    latest_for_task = store.latest_approval_for_task(task.task_id)
    assert latest_for_task is not None
    assert latest_for_task["approval_id"] == approval.approval_id


def test_task_store_rejects_unknown_task_status_update(tmp_path):
    store = TaskStore(tmp_path / "server.sqlite3")
    try:
        store.update_task_status("task_missing", TaskStatus.COMPLETED)
    except ValidationError as exc:
        assert "unknown task" in exc.envelope.message
        assert exc.envelope.details["task_id"] == "task_missing"
    else:
        raise AssertionError("expected ValidationError")


def test_task_store_rejects_invalid_status_transition(tmp_path):
    store = TaskStore(tmp_path / "server.sqlite3")
    task = store.create_task(TaskCreate(content="check", device_id="pc-1"))
    try:
        store.update_task_status(task.task_id, TaskStatus.COMPLETED)
    except ValidationError as exc:
        assert "Invalid task status transition" in exc.envelope.message
        assert exc.envelope.details["current_status"] == "pending"
        assert exc.envelope.details["target_status"] == "completed"
    else:
        raise AssertionError("expected ValidationError")


def test_task_store_allows_worker_status_path(tmp_path):
    store = TaskStore(tmp_path / "server.sqlite3")
    task = store.create_task(TaskCreate(content="check", device_id="pc-1"))
    claimed = store.claim_pending("pc-1")
    assert claimed[0]["task_id"] == task.task_id
    store.update_task_status(task.task_id, TaskStatus.WAITING_APPROVAL)
    store.update_task_status(task.task_id, TaskStatus.PENDING)
    store.claim_pending("pc-1")
    store.update_task_status(task.task_id, TaskStatus.COMPLETED)
    run = store.get_run("missing_run")
    assert run["diagnostics"]["status"] == "not_found"


def test_task_store_redacts_cloud_persisted_payloads(tmp_path):
    db_path = tmp_path / "server.sqlite3"
    store = TaskStore(db_path)
    secret = "sk-abcdefghijklmnopqrstuvwxyz"

    task = store.create_task(
        TaskCreate(
            content=f"please use {secret}",
            device_id="pc-1",
        )
    )
    claimed = store.claim_pending("pc-1")
    assert claimed[0]["content"] == "please use [REDACTED]"

    store.append_event(
        RunEvent(
            task_id=task.task_id,
            run_id="run_secret",
            agent="tester",
            event_type=EventType.RUN_FAILED,
            summary=f"failed with Bearer abcdefghijklmnop",
            details={"api_key": secret, "note": f"token {secret}"},
        )
    )
    store.record_approval(
        ApprovalRecord(
            task_id=task.task_id,
            run_id="run_secret",
            decision="approved",
            approved_by=f"operator {secret}",
        )
    )
    store.heartbeat("pc-1", {"token": secret, "status": "online"})

    conn = sqlite3.connect(db_path)
    try:
        persisted = "\n".join(
            item
            for item in [
                conn.execute("select content from tasks").fetchone()[0],
                conn.execute("select payload_json from events").fetchone()[0],
                conn.execute("select payload_json from approvals").fetchone()[0],
                conn.execute("select payload_json from heartbeats").fetchone()[0],
            ]
        )
    finally:
        conn.close()
    assert secret not in persisted
    assert "[REDACTED]" in persisted

    run = store.get_run("run_secret")
    assert secret not in json.dumps(run, ensure_ascii=False)
