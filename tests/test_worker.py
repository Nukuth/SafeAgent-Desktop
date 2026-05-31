from __future__ import annotations

import asyncio
from types import SimpleNamespace

from safeagent.local_worker.orchestrator import OrchestratorResult
from safeagent.local_worker.policy import PolicyDecision
from safeagent.local_worker.worker import LocalWorker
from safeagent.shared.enums import EventType, RiskLevel, TaskStatus
from safeagent.shared.errors import ValidationError
from safeagent.shared.schemas import RunEvent


class MemoryAudit:
    def __init__(self) -> None:
        self.writes: list[dict[str, object]] = []

    def write(self, event: dict[str, object]) -> None:
        self.writes.append(event)


class FakeClient:
    def __init__(
        self,
        tasks: list[dict[str, object]],
        *,
        fail_post_for: set[str] | None = None,
        fail_status_for: set[str] | None = None,
    ) -> None:
        self.tasks = tasks
        self.fail_post_for = fail_post_for or set()
        self.fail_status_for = fail_status_for or set()
        self.posted_events: list[RunEvent] = []
        self.status_updates: list[tuple[str, TaskStatus]] = []
        self.heartbeats: list[tuple[str, dict[str, object]]] = []

    async def fetch_pending(self, device_id: str) -> list[dict[str, object]]:
        return self.tasks

    async def heartbeat(self, task_id: str, payload: dict[str, object]) -> None:
        self.heartbeats.append((task_id, payload))

    async def fetch_latest_approval(self, task_id: str) -> dict[str, object] | None:
        return None

    async def post_event(self, event: RunEvent) -> None:
        if event.task_id in self.fail_post_for:
            raise RuntimeError("cloud event endpoint unavailable")
        self.posted_events.append(event)

    async def update_status(self, task_id: str, status: TaskStatus) -> None:
        if task_id in self.fail_status_for:
            raise RuntimeError("cloud status endpoint unavailable")
        self.status_updates.append((task_id, status))


class IsolatingOrchestrator:
    def handle_task(
        self,
        task: dict[str, object],
        approval: dict[str, object] | None = None,
    ) -> OrchestratorResult:
        task_id = str(task["task_id"])
        if task_id == "task_bad":
            raise ValidationError(
                "local_worker.test",
                "bad task secret=sk-123456789012",
                {"api_key": "sk-123456789012"},
            )
        policy = PolicyDecision(
            allowed=True,
            risk_level=RiskLevel.LOW,
            requires_local_confirmation=False,
            reasons=["test task"],
        )
        return OrchestratorResult(
            run_id=f"run_{task_id}",
            status=TaskStatus.COMPLETED,
            events=[
                RunEvent(
                    task_id=task_id,
                    run_id=f"run_{task_id}",
                    agent="summarizer",
                    event_type=EventType.RUN_COMPLETED,
                    summary="task completed",
                )
            ],
            policy=policy,
            plan_hash=f"hash_{task_id}",
        )


def make_worker(client: FakeClient) -> LocalWorker:
    worker = object.__new__(LocalWorker)
    worker.settings = SimpleNamespace(device_id="device_1", poll_interval_seconds=5.0)
    worker.audit = MemoryAudit()
    worker.client = client
    worker.orchestrator = IsolatingOrchestrator()
    return worker


def test_worker_isolates_failed_task_and_continues_same_poll_batch():
    client = FakeClient(
        [
            {"task_id": "task_bad", "content": "break"},
            {"task_id": "task_ok", "content": "continue"},
        ]
    )
    worker = make_worker(client)

    assert asyncio.run(worker.run_once()) == 2

    assert client.status_updates == [
        ("task_bad", TaskStatus.FAILED),
        ("task_ok", TaskStatus.COMPLETED),
    ]
    assert [heartbeat[1]["phase"] for heartbeat in client.heartbeats] == ["poll_started", "poll_completed"]
    assert client.heartbeats[-1][1]["task_count"] == 2
    posted_types = [(event.task_id, event.event_type) for event in client.posted_events]
    assert ("task_bad", EventType.RUN_FAILED) in posted_types
    assert ("task_ok", EventType.RUN_COMPLETED) in posted_types
    failed_audit = [event for event in worker.audit.writes if event.get("event") == "task_failed"]
    assert failed_audit
    assert failed_audit[0]["error"]["code"] == "validation.failed"  # type: ignore[index]
    assert "sk-123456789012" not in str(worker.audit.writes)


def test_worker_failure_reporting_is_best_effort_and_does_not_block_next_task():
    client = FakeClient(
        [
            {"task_id": "task_bad", "content": "break"},
            {"task_id": "task_ok", "content": "continue"},
        ],
        fail_post_for={"task_bad"},
        fail_status_for={"task_bad"},
    )
    worker = make_worker(client)

    assert asyncio.run(worker.run_once()) == 2

    assert client.status_updates == [("task_ok", TaskStatus.COMPLETED)]
    assert any(event.get("event") == "task_failure_report_failed" for event in worker.audit.writes)
    assert any(event.task_id == "task_ok" for event in client.posted_events)


def test_worker_heartbeat_failure_is_logged_without_blocking_poll_batch():
    class FailingHeartbeatClient(FakeClient):
        async def heartbeat(self, task_id: str, payload: dict[str, object]) -> None:
            raise RuntimeError("heartbeat endpoint unavailable")

    client = FailingHeartbeatClient([{"task_id": "task_ok", "content": "continue"}])
    worker = make_worker(client)

    assert asyncio.run(worker.run_once()) == 1

    assert client.status_updates == [("task_ok", TaskStatus.COMPLETED)]
    failures = [event for event in worker.audit.writes if event.get("event") == "heartbeat_failed"]
    assert len(failures) == 2
