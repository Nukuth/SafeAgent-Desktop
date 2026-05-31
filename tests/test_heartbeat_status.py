from __future__ import annotations

from datetime import UTC, datetime, timedelta

from safeagent.shared.heartbeat_status import build_device_heartbeat_view


def test_device_heartbeat_view_marks_fresh_heartbeat_online():
    now = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    view = build_device_heartbeat_view(
        "pc-1",
        {"phase": "poll_completed", "updated_at": (now - timedelta(seconds=5)).isoformat()},
        stale_after_seconds=60,
        now=now,
    )

    assert view["device_status"] == "online"
    assert view["age_seconds"] == 5.0
    assert view["heartbeat"]["phase"] == "poll_completed"


def test_device_heartbeat_view_marks_old_heartbeat_stale():
    now = datetime(2026, 5, 31, 12, 0, 0, tzinfo=UTC)
    view = build_device_heartbeat_view(
        "pc-1",
        {"phase": "poll_completed", "updated_at": (now - timedelta(seconds=90)).isoformat()},
        stale_after_seconds=60,
        now=now,
    )

    assert view["device_status"] == "stale"
    assert view["age_seconds"] == 90.0


def test_device_heartbeat_view_handles_missing_and_invalid_heartbeat():
    missing = build_device_heartbeat_view("pc-1", None)
    assert missing["device_status"] == "never_seen"
    assert missing["heartbeat"] is None

    invalid = build_device_heartbeat_view("pc-1", {"updated_at": "not-a-date"})
    assert invalid["device_status"] == "stale"
    assert invalid["age_seconds"] is None
    assert invalid["status_reason"] == "invalid_updated_at"
