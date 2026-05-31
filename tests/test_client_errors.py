from __future__ import annotations

from safeagent.local_worker.client import raise_for_control_plane_error
from safeagent.shared.errors import SafeAgentError


class FakeResponse:
    def __init__(self, status_code: int, payload: object | None = None, text: str = "") -> None:
        self.status_code = status_code
        self.payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> object:
        if self.payload is None:
            raise ValueError("not json")
        return self.payload


def test_control_plane_client_preserves_server_error_envelope():
    response = FakeResponse(
        400,
        {
            "error": {
                "code": "auth.failed",
                "module": "shared.auth",
                "message": "Authentication failed",
                "severity": "warning",
                "retriable": False,
                "details": {"token": "secret-token"},
            }
        },
    )

    try:
        raise_for_control_plane_error(response, "fetch_pending")
    except SafeAgentError as exc:
        assert exc.envelope.code == "auth.failed"
        assert exc.envelope.module == "shared.auth"
        assert exc.envelope.severity.value == "warning"
        assert exc.envelope.retriable is False
        assert exc.envelope.details["client_operation"] == "fetch_pending"
        assert exc.envelope.details["token"] == "[REDACTED]"
    else:
        raise AssertionError("expected SafeAgentError")


def test_control_plane_client_maps_plain_4xx_to_validation_error():
    response = FakeResponse(422, None, "bad request with sk-abcdefghijklmnopqrstuvwxyz")

    try:
        raise_for_control_plane_error(response, "post_event")
    except SafeAgentError as exc:
        assert exc.envelope.code == "validation.failed"
        assert exc.envelope.module == "local_worker.client"
        assert exc.envelope.retriable is False
        assert exc.envelope.details["operation"] == "post_event"
        assert exc.envelope.details["response_text"] == "bad request with [REDACTED]"
    else:
        raise AssertionError("expected SafeAgentError")


def test_control_plane_client_maps_plain_5xx_to_transient_upstream():
    response = FakeResponse(503, None, "service unavailable")

    try:
        raise_for_control_plane_error(response, "update_status")
    except SafeAgentError as exc:
        assert exc.envelope.code == "upstream.transient"
        assert exc.envelope.module == "local_worker.client"
        assert exc.envelope.retriable is True
        assert exc.envelope.details["operation"] == "update_status"
        assert exc.envelope.details["http_status"] == 503
    else:
        raise AssertionError("expected SafeAgentError")
