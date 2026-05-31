from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Any

from safeagent.shared.enums import TaskStatus
from safeagent.shared.diagnostics import build_run_diagnostics
from safeagent.shared.errors import ValidationError
from safeagent.shared.redaction import redact_payload
from safeagent.shared.schemas import ApprovalRecord, RunEvent, TaskCreate, TaskRecord
from safeagent.shared.task_lifecycle import is_valid_task_status_transition
from safeagent.shared.time import utc_now_iso


class TaskStore:
    """SQLite-backed control-plane store.

    The cloud store intentionally keeps only task metadata and redacted events.
    It must not store provider API keys or full local execution logs.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                create table if not exists tasks (
                    task_id text primary key,
                    device_id text not null,
                    content text not null,
                    status text not null,
                    source text not null,
                    requested_profile text,
                    remote_permission text not null,
                    created_at text not null,
                    updated_at text not null
                );

                create index if not exists idx_tasks_device_status
                    on tasks(device_id, status, created_at);

                create table if not exists events (
                    event_id text primary key,
                    task_id text not null,
                    run_id text not null,
                    payload_json text not null,
                    created_at text not null
                );

                create table if not exists approvals (
                    approval_id text primary key,
                    task_id text not null,
                    run_id text not null,
                    payload_json text not null,
                    created_at text not null
                );

                create table if not exists heartbeats (
                    device_id text primary key,
                    payload_json text not null,
                    updated_at text not null
                );
                """
            )

    def create_task(self, task: TaskCreate) -> TaskRecord:
        if not task.content.strip():
            raise ValidationError("server.db", "Task content cannot be empty")
        redacted_task = TaskCreate(
            content=str(redact_payload(task.content)),
            device_id=task.device_id,
            requested_profile=task.requested_profile,
            remote_permission=task.remote_permission,
        )
        record = TaskRecord.create(redacted_task)
        with self._connection() as conn:
            conn.execute(
                """
                insert into tasks (
                    task_id, device_id, content, status, source, requested_profile,
                    remote_permission, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.task_id,
                    record.device_id,
                    record.content,
                    record.status.value,
                    record.source,
                    record.requested_profile,
                    record.remote_permission.value,
                    record.created_at,
                    record.updated_at,
                ),
            )
        return record

    def claim_pending(self, device_id: str, limit: int = 5) -> list[dict[str, Any]]:
        now = utc_now_iso()
        with self._connection() as conn:
            rows = conn.execute(
                """
                select * from tasks
                where device_id = ? and status = ?
                order by created_at asc
                limit ?
                """,
                (device_id, TaskStatus.PENDING.value, limit),
            ).fetchall()
            task_ids = [row["task_id"] for row in rows]
            if task_ids:
                conn.executemany(
                    "update tasks set status = ?, updated_at = ? where task_id = ?",
                    [(TaskStatus.CLAIMED.value, now, task_id) for task_id in task_ids],
                )
        return [dict(row) for row in rows]

    def list_tasks(
        self,
        device_id: str | None = None,
        status: TaskStatus | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if device_id:
            clauses.append("device_id = ?")
            params.append(device_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value)
        where = f"where {' and '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 200)))
        with self._connection() as conn:
            rows = conn.execute(
                f"""
                select * from tasks
                {where}
                order by updated_at desc, created_at desc
                limit ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_task_detail(self, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            task = conn.execute("select * from tasks where task_id = ?", (task_id,)).fetchone()
            if task is None:
                return None
            events = conn.execute(
                "select payload_json from events where task_id = ? order by created_at asc",
                (task_id,),
            ).fetchall()
            approvals = conn.execute(
                "select payload_json from approvals where task_id = ? order by created_at asc",
                (task_id,),
            ).fetchall()
        event_payloads = [json.loads(row["payload_json"]) for row in events]
        approval_payloads = [json.loads(row["payload_json"]) for row in approvals]
        return {
            "task": dict(task),
            "events": event_payloads,
            "approvals": approval_payloads,
            "run_ids": _ordered_run_ids(event_payloads, approval_payloads),
        }

    def update_task_status(self, task_id: str, status: TaskStatus) -> None:
        with self._connection() as conn:
            row = conn.execute("select status from tasks where task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise ValidationError(
                    "server.db",
                    "Cannot update status for unknown task",
                    {"task_id": task_id, "target_status": status.value},
                )
            current = TaskStatus(row["status"])
            if not is_valid_task_status_transition(current, status):
                raise ValidationError(
                    "server.db",
                    "Invalid task status transition",
                    {
                        "task_id": task_id,
                        "current_status": current.value,
                        "target_status": status.value,
                    },
                )
            conn.execute(
                "update tasks set status = ?, updated_at = ? where task_id = ?",
                (status.value, utc_now_iso(), task_id),
            )

    def append_event(self, event: RunEvent) -> None:
        payload = redact_payload(event.to_dict())
        with self._connection() as conn:
            conn.execute(
                "insert into events(event_id, task_id, run_id, payload_json, created_at) values (?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.task_id,
                    event.run_id,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    event.created_at,
                ),
            )

    def record_approval(self, approval: ApprovalRecord) -> None:
        payload = redact_payload(approval.to_dict())
        with self._connection() as conn:
            conn.execute(
                "insert into approvals(approval_id, task_id, run_id, payload_json, created_at) values (?, ?, ?, ?, ?)",
                (
                    approval.approval_id,
                    approval.task_id,
                    approval.run_id,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    approval.created_at,
                ),
            )

    def latest_approval(self, task_id: str, run_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                select payload_json from approvals
                where task_id = ? and run_id = ?
                order by created_at desc
                limit 1
                """,
                (task_id, run_id),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def latest_approval_for_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                select payload_json from approvals
                where task_id = ?
                order by created_at desc
                limit 1
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["payload_json"])

    def heartbeat(self, device_id: str, payload: dict[str, Any]) -> None:
        now = utc_now_iso()
        redacted_payload = redact_payload(payload)
        with self._connection() as conn:
            conn.execute(
                """
                insert into heartbeats(device_id, payload_json, updated_at)
                values (?, ?, ?)
                on conflict(device_id) do update set
                    payload_json = excluded.payload_json,
                    updated_at = excluded.updated_at
                """,
                (device_id, json.dumps(redacted_payload, ensure_ascii=False, sort_keys=True), now),
            )

    def latest_heartbeat(self, device_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                "select payload_json, updated_at from heartbeats where device_id = ?",
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        payload = json.loads(row["payload_json"])
        if isinstance(payload, dict):
            return {**payload, "updated_at": row["updated_at"]}
        return {"payload": payload, "updated_at": row["updated_at"]}

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._connection() as conn:
            events = conn.execute(
                "select payload_json from events where run_id = ? order by created_at asc",
                (run_id,),
            ).fetchall()
            approvals = conn.execute(
                "select payload_json from approvals where run_id = ? order by created_at asc",
                (run_id,),
            ).fetchall()
        event_payloads = [json.loads(row["payload_json"]) for row in events]
        approval_payloads = [json.loads(row["payload_json"]) for row in approvals]
        return {
            "run_id": run_id,
            "events": event_payloads,
            "approvals": approval_payloads,
            "diagnostics": build_run_diagnostics(event_payloads, approval_payloads),
        }


def _ordered_run_ids(events: list[dict[str, Any]], approvals: list[dict[str, Any]]) -> list[str]:
    run_ids: list[str] = []
    for payload in [*events, *approvals]:
        run_id = payload.get("run_id")
        if isinstance(run_id, str) and run_id and run_id not in run_ids:
            run_ids.append(run_id)
    return run_ids
