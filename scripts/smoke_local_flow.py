from __future__ import annotations

import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.orchestrator import LocalOrchestrator  # noqa: E402
from safeagent.local_worker.policy import PolicyEngine  # noqa: E402
from safeagent.local_worker.registry import load_default_registries  # noqa: E402
from safeagent.server.db import TaskStore  # noqa: E402
from safeagent.shared.enums import TaskStatus  # noqa: E402
from safeagent.shared.schemas import ApprovalRecord, TaskCreate  # noqa: E402


def run_smoke(root: Path, temp_dir: Path) -> dict[str, Any]:
    store = TaskStore(temp_dir / "server.sqlite3")
    agents, profiles = load_default_registries(root / "configs")
    orchestrator = LocalOrchestrator(
        PolicyEngine(root),
        agent_registry=agents,
        profile_registry=profiles,
    )

    medium_task = store.create_task(
        TaskCreate(
            content="copy-item E:\\agents\\a E:\\agents\\b",
            device_id="local-pc-1",
            requested_profile="safe_shell",
        )
    )
    claimed = store.claim_pending("local-pc-1")
    assert len(claimed) == 1, "expected medium-risk task to be claimed"

    first = orchestrator.handle_task(claimed[0])
    for event in first.events:
        store.append_event(event)
    store.update_task_status(medium_task.task_id, first.status)
    assert first.status == TaskStatus.WAITING_APPROVAL, "medium-risk task should wait for approval"

    approval = ApprovalRecord(
        task_id=medium_task.task_id,
        run_id=first.run_id,
        decision="approved",
        approved_by="smoke-test",
        approval_scope="plan_only",
        plan_hash=first.plan_hash,
        expires_at=(datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    )
    store.record_approval(approval)
    store.update_task_status(medium_task.task_id, TaskStatus.PENDING)

    reclaimed = store.claim_pending("local-pc-1")
    assert len(reclaimed) == 1, "approved task should be re-queued and claimed"
    second = orchestrator.handle_task(
        reclaimed[0],
        approval=store.latest_approval_for_task(medium_task.task_id),
    )
    for event in second.events:
        store.append_event(event)
    store.update_task_status(medium_task.task_id, second.status)
    assert second.status == TaskStatus.COMPLETED, "valid approval should complete dry-run"
    assert second.plan_hash == first.plan_hash, "plan_hash should stay stable across approval re-run"

    high_task = store.create_task(
        TaskCreate(
            content="执行 diskpart 修改分区",
            device_id="local-pc-1",
            requested_profile="safe_shell",
        )
    )
    high_claimed = store.claim_pending("local-pc-1")
    assert len(high_claimed) == 1, "expected high-risk task to be claimed"
    high = orchestrator.handle_task(high_claimed[0])
    for event in high.events:
        store.append_event(event)
    store.update_task_status(high_task.task_id, high.status)
    assert high.status == TaskStatus.BLOCKED, "high-risk task should be blocked"

    run = store.get_run(second.run_id)
    assert run["events"], "completed run should have stored events"

    return {
        "medium_task_id": medium_task.task_id,
        "first_run_id": first.run_id,
        "second_run_id": second.run_id,
        "high_task_id": high_task.task_id,
        "medium_status": second.status.value,
        "high_status": high.status.value,
        "plan_hash": second.plan_hash,
        "events_recorded": len(run["events"]),
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        try:
            result = run_smoke(ROOT, Path(temp))
        except AssertionError as exc:
            print(f"FAIL smoke_local_flow: {exc}", file=sys.stderr)
            return 1
    print("OK local smoke flow")
    for key in sorted(result):
        print(f"{key}={result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
