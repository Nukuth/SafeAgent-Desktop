from __future__ import annotations

import os
from contextlib import contextmanager

from fastapi.testclient import TestClient

from safeagent.server.app import create_app


@contextmanager
def patched_env(values: dict[str, str]):
    original = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def make_client(tmp_path) -> TestClient:
    return TestClient(create_app())


def remote_headers(permission: str = "submit_task") -> dict[str, str]:
    return {
        "Authorization": "Bearer remote-token",
        "X-SafeAgent-Remote-Permission": permission,
    }


def worker_headers() -> dict[str, str]:
    return {"Authorization": "Bearer worker-token"}


def assert_auth_failed(response) -> None:
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "auth.failed"


def test_remote_and_worker_tokens_are_separate_api_boundaries(tmp_path):
    with patched_env(
        {
            "SAFEAGENT_SERVER_TOKEN": "remote-token",
            "SAFEAGENT_WORKER_TOKEN": "worker-token",
            "SAFEAGENT_DB_PATH": str(tmp_path / "server.sqlite3"),
        }
    ):
        client = make_client(tmp_path)

        task_response = client.post(
            "/api/tasks",
            headers=remote_headers(),
            json={
                "content": "inspect workspace",
                "device_id": "pc-1",
                "requested_profile": "safe_shell",
                "remote_permission": "submit_task",
            },
        )
        assert task_response.status_code == 200
        task_id = task_response.json()["task"]["task_id"]

        worker_task_create = client.post(
            "/api/tasks",
            headers=worker_headers(),
            json={
                "content": "worker should not submit remote tasks",
                "device_id": "pc-1",
                "remote_permission": "submit_task",
            },
        )
        assert_auth_failed(worker_task_create)

        assert_auth_failed(client.get("/api/tasks/pending?device_id=pc-1", headers=remote_headers()))
        pending = client.get("/api/tasks/pending?device_id=pc-1", headers=worker_headers())
        assert pending.status_code == 200
        assert pending.json()["tasks"][0]["task_id"] == task_id

        event_payload = {
            "run_id": "run_1",
            "agent": "tester",
            "event_type": "run_completed",
            "summary": "done",
            "risk_level": "low",
            "network_mode": "api_only",
            "details": {},
        }
        assert_auth_failed(client.post(f"/api/tasks/{task_id}/events", headers=remote_headers(), json=event_payload))
        event_response = client.post(f"/api/tasks/{task_id}/events", headers=worker_headers(), json=event_payload)
        assert event_response.status_code == 200

        assert_auth_failed(client.get(f"/api/tasks/{task_id}/approval/latest", headers=remote_headers()))
        latest_approval = client.get(f"/api/tasks/{task_id}/approval/latest", headers=worker_headers())
        assert latest_approval.status_code == 200
        assert latest_approval.json()["approval"] is None

        assert_auth_failed(
            client.post(f"/api/tasks/{task_id}/status", headers=remote_headers(), json={"status": "completed"})
        )
        status_response = client.post(
            f"/api/tasks/{task_id}/status", headers=worker_headers(), json={"status": "completed"}
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "completed"


def test_remote_approval_is_not_a_worker_route(tmp_path):
    with patched_env(
        {
            "SAFEAGENT_SERVER_TOKEN": "remote-token",
            "SAFEAGENT_WORKER_TOKEN": "worker-token",
            "SAFEAGENT_DB_PATH": str(tmp_path / "server.sqlite3"),
        }
    ):
        client = make_client(tmp_path)
        task_response = client.post(
            "/api/tasks",
            headers=remote_headers(),
            json={
                "content": "copy item requires approval",
                "device_id": "pc-1",
                "remote_permission": "submit_task",
            },
        )
        assert task_response.status_code == 200
        task_id = task_response.json()["task"]["task_id"]

        approval_response = client.post(
            f"/api/tasks/{task_id}/approval",
            headers=remote_headers("approval_only"),
            json={
                "run_id": "run_1",
                "decision": "rejected",
                "approved_by": "operator",
                "approval_scope": "plan_only",
            },
        )
        assert approval_response.status_code == 200
        assert approval_response.json()["approval"]["decision"] == "rejected"

        assert_auth_failed(
            client.post(
                f"/api/tasks/{task_id}/approval",
                headers=worker_headers(),
                json={
                    "run_id": "run_1",
                    "decision": "approved",
                    "approved_by": "worker",
                    "approval_scope": "plan_only",
                },
            )
        )
