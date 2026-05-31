from safeagent.shared.enums import TaskStatus
from safeagent.shared.task_lifecycle import is_valid_task_status_transition


def test_task_status_lifecycle_allows_worker_and_approval_path():
    assert is_valid_task_status_transition(TaskStatus.PENDING, TaskStatus.CLAIMED)
    assert is_valid_task_status_transition(TaskStatus.CLAIMED, TaskStatus.WAITING_APPROVAL)
    assert is_valid_task_status_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.PENDING)
    assert is_valid_task_status_transition(TaskStatus.CLAIMED, TaskStatus.COMPLETED)
    assert is_valid_task_status_transition(TaskStatus.CLAIMED, TaskStatus.BLOCKED)
    assert is_valid_task_status_transition(TaskStatus.CLAIMED, TaskStatus.FAILED)


def test_task_status_lifecycle_rejects_terminal_reopen():
    assert not is_valid_task_status_transition(TaskStatus.COMPLETED, TaskStatus.PENDING)
    assert not is_valid_task_status_transition(TaskStatus.BLOCKED, TaskStatus.PENDING)
    assert not is_valid_task_status_transition(TaskStatus.FAILED, TaskStatus.CLAIMED)
    assert not is_valid_task_status_transition(TaskStatus.REJECTED, TaskStatus.PENDING)


def test_task_status_lifecycle_rejects_direct_remote_completion():
    assert not is_valid_task_status_transition(TaskStatus.PENDING, TaskStatus.COMPLETED)
    assert not is_valid_task_status_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.COMPLETED)
