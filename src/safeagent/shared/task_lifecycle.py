from __future__ import annotations

from safeagent.shared.enums import TaskStatus


ALLOWED_TASK_STATUS_TRANSITIONS = {
    TaskStatus.PENDING: frozenset({TaskStatus.CLAIMED, TaskStatus.REJECTED}),
    TaskStatus.CLAIMED: frozenset(
        {
            TaskStatus.RUNNING,
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
        }
    ),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.WAITING_APPROVAL,
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.BLOCKED,
            TaskStatus.REJECTED,
        }
    ),
    TaskStatus.WAITING_APPROVAL: frozenset({TaskStatus.PENDING, TaskStatus.REJECTED}),
    TaskStatus.COMPLETED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.BLOCKED: frozenset(),
    TaskStatus.REJECTED: frozenset(),
}


def is_valid_task_status_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target == current or target in ALLOWED_TASK_STATUS_TRANSITIONS[current]
