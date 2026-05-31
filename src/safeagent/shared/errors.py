from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from safeagent.shared.enums import Severity


@dataclass(slots=True)
class ErrorEnvelope:
    code: str
    module: str
    message: str
    severity: Severity = Severity.ERROR
    retriable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity"] = self.severity.value
        return data


class SafeAgentError(Exception):
    """Base error with a stable, loggable envelope."""

    def __init__(
        self,
        code: str,
        module: str,
        message: str,
        *,
        severity: Severity = Severity.ERROR,
        retriable: bool = False,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.envelope = ErrorEnvelope(
            code=code,
            module=module,
            message=message,
            severity=severity,
            retriable=retriable,
            details=details or {},
        )


class AuthError(SafeAgentError):
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(
            "auth.failed",
            "shared.auth",
            message,
            severity=Severity.WARNING,
            retriable=False,
        )


class ValidationError(SafeAgentError):
    def __init__(self, module: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "validation.failed",
            module,
            message,
            severity=Severity.WARNING,
            retriable=False,
            details=details,
        )


class PolicyDeniedError(SafeAgentError):
    def __init__(self, module: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "policy.denied",
            module,
            message,
            severity=Severity.ERROR,
            retriable=False,
            details=details,
        )


class DependencyMissingError(SafeAgentError):
    def __init__(self, module: str, dependency: str, install_hint: str) -> None:
        super().__init__(
            "dependency.missing",
            module,
            f"Required dependency is not installed: {dependency}",
            severity=Severity.WARNING,
            retriable=False,
            details={"dependency": dependency, "install_hint": install_hint},
        )


class TransientUpstreamError(SafeAgentError):
    def __init__(self, module: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            "upstream.transient",
            module,
            message,
            severity=Severity.ERROR,
            retriable=True,
            details=details,
        )
