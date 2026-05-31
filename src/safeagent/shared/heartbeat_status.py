from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

DEFAULT_HEARTBEAT_STALE_AFTER_SECONDS = 60

DEVICE_STATUS_ONLINE = "online"
DEVICE_STATUS_STALE = "stale"
DEVICE_STATUS_NEVER_SEEN = "never_seen"


def build_device_heartbeat_view(
    device_id: str,
    heartbeat: dict[str, Any] | None,
    stale_after_seconds: int = DEFAULT_HEARTBEAT_STALE_AFTER_SECONDS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a UI-safe device heartbeat view without mutating stored heartbeat data."""

    effective_stale_after = max(1, stale_after_seconds)
    if heartbeat is None:
        return {
            "device_id": device_id,
            "device_status": DEVICE_STATUS_NEVER_SEEN,
            "heartbeat": None,
            "age_seconds": None,
            "stale_after_seconds": effective_stale_after,
        }

    observed_at = _parse_utc_datetime(str(heartbeat.get("updated_at", "")))
    if observed_at is None:
        return {
            "device_id": device_id,
            "device_status": DEVICE_STATUS_STALE,
            "heartbeat": heartbeat,
            "age_seconds": None,
            "stale_after_seconds": effective_stale_after,
            "status_reason": "invalid_updated_at",
        }

    current_time = _as_utc(now or datetime.now(UTC))
    age_seconds = max(0.0, (current_time - observed_at).total_seconds())
    return {
        "device_id": device_id,
        "device_status": DEVICE_STATUS_ONLINE if age_seconds <= effective_stale_after else DEVICE_STATUS_STALE,
        "heartbeat": heartbeat,
        "age_seconds": round(age_seconds, 3),
        "stale_after_seconds": effective_stale_after,
    }


def _parse_utc_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
