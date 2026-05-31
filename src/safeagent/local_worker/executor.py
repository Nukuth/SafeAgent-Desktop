from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from safeagent.local_worker.policy import PolicyDecision, PolicyEngine, max_risk
from safeagent.shared.enums import RiskLevel
from safeagent.shared.errors import PolicyDeniedError, ValidationError
from safeagent.shared.plan_hash import compute_plan_hash
from safeagent.shared.redaction import redact_text


ALLOWED_READONLY_COMMANDS = {
    "Get-ChildItem",
    "Get-Item",
    "Get-Content",
    "Select-String",
    "Test-Path",
}

LIVE_READONLY_COMMANDS = {
    "Get-ChildItem",
    "Get-Item",
    "Test-Path",
}

DENIED_COMMANDS = {
    "Remove-Item",
    "del",
    "rmdir",
    "diskpart",
    "format",
    "bcdedit",
    "bootrec",
    "reg",
    "fastboot",
    "adb",
    "Invoke-WebRequest",
    "curl",
    "Start-Process",
}

UNSAFE_LIVE_ARG_RE = re.compile(r"[;&|><`$(){}\r\n]")


@dataclass(frozen=True, slots=True)
class CommandProposal:
    command: str
    args: tuple[str, ...] = ()
    cwd: str | None = None
    reason: str = ""
    expected_risk: RiskLevel = RiskLevel.LOW

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "args": list(self.args),
            "cwd": self.cwd,
            "reason": self.reason,
            "expected_risk": self.expected_risk.value,
            "command_hash": command_fingerprint(self),
        }


@dataclass(frozen=True, slots=True)
class CommandValidation:
    allowed: bool
    dry_run_only: bool
    risk_level: RiskLevel
    command_hash: str
    execution_mode: str = "dry_run"
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "dry_run_only": self.dry_run_only,
            "risk_level": self.risk_level.value,
            "command_hash": self.command_hash,
            "execution_mode": self.execution_mode,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ExecutionOutputAudit:
    stdout_truncated: bool
    stderr_truncated: bool
    stdout_original_chars: int
    stderr_original_chars: int
    stdout_limit_chars: int
    stderr_limit_chars: int

    def to_dict(self) -> dict[str, object]:
        return {
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "stdout_original_chars": self.stdout_original_chars,
            "stderr_original_chars": self.stderr_original_chars,
            "stdout_limit_chars": self.stdout_limit_chars,
            "stderr_limit_chars": self.stderr_limit_chars,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    executed: bool
    exit_code: int | None
    stdout: str
    stderr: str
    execution_mode: str
    timeout_seconds: float
    output_audit: ExecutionOutputAudit
    validation: CommandValidation

    def to_dict(self) -> dict[str, object]:
        return {
            "executed": self.executed,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_mode": self.execution_mode,
            "timeout_seconds": self.timeout_seconds,
            "output_audit": self.output_audit.to_dict(),
            "validation": self.validation.to_dict(),
        }


class CommandValidator:
    def __init__(
        self,
        workspace_root: Path,
        policy_engine: PolicyEngine,
        allow_live_readonly: bool = False,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.policy_engine = policy_engine
        self.allow_live_readonly = allow_live_readonly

    def validate(self, proposal: CommandProposal, execution_mode: str = "dry_run") -> CommandValidation:
        reasons: list[str] = []
        command = proposal.command.strip()
        if not command:
            raise ValidationError("local_worker.executor", "Command proposal has empty command")

        command_hash = command_fingerprint(proposal)
        risk = proposal.expected_risk
        policy: PolicyDecision = self.policy_engine.evaluate_task(" ".join([command, *proposal.args]))
        risk = max_risk(risk, policy.risk_level)
        reasons.extend(policy.reasons)

        if command in DENIED_COMMANDS:
            return CommandValidation(
                allowed=False,
                dry_run_only=True,
                risk_level=max_risk(risk, RiskLevel.HIGH),
                command_hash=command_hash,
                execution_mode=execution_mode,
                reasons=tuple([*reasons, f"command is explicitly denied: {command}"]),
            )

        if command not in ALLOWED_READONLY_COMMANDS:
            return CommandValidation(
                allowed=False,
                dry_run_only=True,
                risk_level=max_risk(risk, RiskLevel.MEDIUM),
                command_hash=command_hash,
                execution_mode=execution_mode,
                reasons=tuple([*reasons, f"command is not in read-only allowlist: {command}"]),
            )

        cwd = Path(proposal.cwd).resolve() if proposal.cwd else self.workspace_root
        if not _is_relative_to(cwd, self.workspace_root):
            return CommandValidation(
                allowed=False,
                dry_run_only=True,
                risk_level=max_risk(risk, RiskLevel.HIGH),
                command_hash=command_hash,
                execution_mode=execution_mode,
                reasons=tuple([*reasons, f"cwd must stay under workspace root: {self.workspace_root}"]),
            )

        if execution_mode != "dry_run":
            if execution_mode != "live_readonly":
                return CommandValidation(
                    allowed=False,
                    dry_run_only=True,
                    risk_level=max_risk(risk, RiskLevel.MEDIUM),
                    command_hash=command_hash,
                    execution_mode=execution_mode,
                    reasons=tuple([*reasons, f"unsupported execution_mode: {execution_mode}"]),
                )
            if not self.allow_live_readonly:
                return CommandValidation(
                    allowed=False,
                    dry_run_only=True,
                    risk_level=max_risk(risk, RiskLevel.MEDIUM),
                    command_hash=command_hash,
                    execution_mode=execution_mode,
                    reasons=tuple(
                        [
                            *reasons,
                            "live_readonly requires SAFEAGENT_ENABLE_LIVE_READONLY=true",
                        ]
                    ),
                )
            if command not in LIVE_READONLY_COMMANDS:
                return CommandValidation(
                    allowed=False,
                    dry_run_only=True,
                    risk_level=max_risk(risk, RiskLevel.MEDIUM),
                    command_hash=command_hash,
                    execution_mode=execution_mode,
                    reasons=tuple([*reasons, f"command is not in live read-only allowlist: {command}"]),
                )
            unsafe_arg = first_unsafe_live_arg(proposal.args)
            if unsafe_arg is not None:
                return CommandValidation(
                    allowed=False,
                    dry_run_only=True,
                    risk_level=max_risk(risk, RiskLevel.MEDIUM),
                    command_hash=command_hash,
                    execution_mode=execution_mode,
                    reasons=tuple([*reasons, f"argument is unsafe for live execution: {unsafe_arg}"]),
                )
            return CommandValidation(
                allowed=True,
                dry_run_only=False,
                risk_level=risk,
                command_hash=command_hash,
                execution_mode=execution_mode,
                reasons=tuple([*reasons, "command is allowed for live read-only execution"]),
            )

        return CommandValidation(
            allowed=True,
            dry_run_only=True,
            risk_level=risk,
            command_hash=command_hash,
            execution_mode=execution_mode,
            reasons=tuple([*reasons, "command is allowed only as dry-run in current MVP"]),
        )


class DryRunExecutor:
    def __init__(
        self,
        validator: CommandValidator,
        execution_mode: str = "dry_run",
        stdout_limit_chars: int = 4000,
        stderr_limit_chars: int = 4000,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.validator = validator
        self.execution_mode = execution_mode
        self.stdout_limit_chars = stdout_limit_chars
        self.stderr_limit_chars = stderr_limit_chars
        self.timeout_seconds = timeout_seconds

    def execute(self, proposal: CommandProposal) -> ExecutionResult:
        validation = self.validator.validate(proposal, execution_mode=self.execution_mode)
        if not validation.allowed:
            raise PolicyDeniedError(
                "local_worker.executor",
                "Command proposal was denied by local validator",
                {"proposal": proposal.to_dict(), "validation": validation.to_dict()},
            )
        if not validation.dry_run_only:
            return self._execute_live_readonly(proposal, validation)
        stdout, stderr, output_audit = audit_execution_output(
            stdout="",
            stderr="dry-run only; command was validated but not executed",
            stdout_limit_chars=self.stdout_limit_chars,
            stderr_limit_chars=self.stderr_limit_chars,
        )
        return ExecutionResult(
            executed=False,
            exit_code=None,
            stdout=stdout,
            stderr=stderr,
            execution_mode=self.execution_mode,
            timeout_seconds=self.timeout_seconds,
            output_audit=output_audit,
            validation=validation,
        )

    def _execute_live_readonly(self, proposal: CommandProposal, validation: CommandValidation) -> ExecutionResult:
        try:
            completed = subprocess.run(
                build_live_readonly_process_args(proposal),
                cwd=str(Path(proposal.cwd).resolve()) if proposal.cwd else str(self.validator.workspace_root),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
            )
            stdout, stderr, output_audit = audit_execution_output(
                stdout=completed.stdout,
                stderr=completed.stderr,
                stdout_limit_chars=self.stdout_limit_chars,
                stderr_limit_chars=self.stderr_limit_chars,
            )
            return ExecutionResult(
                executed=True,
                exit_code=completed.returncode,
                stdout=stdout,
                stderr=stderr,
                execution_mode=self.execution_mode,
                timeout_seconds=self.timeout_seconds,
                output_audit=output_audit,
                validation=validation,
            )
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, output_audit = audit_execution_output(
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + "\ncommand timed out",
                stdout_limit_chars=self.stdout_limit_chars,
                stderr_limit_chars=self.stderr_limit_chars,
            )
            return ExecutionResult(
                executed=True,
                exit_code=None,
                stdout=stdout,
                stderr=stderr,
                execution_mode=self.execution_mode,
                timeout_seconds=self.timeout_seconds,
                output_audit=output_audit,
                validation=validation,
            )


def audit_execution_output(
    *,
    stdout: str,
    stderr: str,
    stdout_limit_chars: int,
    stderr_limit_chars: int,
) -> tuple[str, str, ExecutionOutputAudit]:
    redacted_stdout = redact_text(stdout)
    redacted_stderr = redact_text(stderr)
    audited_stdout, stdout_truncated = truncate_text(redacted_stdout, stdout_limit_chars)
    audited_stderr, stderr_truncated = truncate_text(redacted_stderr, stderr_limit_chars)
    return (
        audited_stdout,
        audited_stderr,
        ExecutionOutputAudit(
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            stdout_original_chars=len(redacted_stdout),
            stderr_original_chars=len(redacted_stderr),
            stdout_limit_chars=stdout_limit_chars,
            stderr_limit_chars=stderr_limit_chars,
        ),
    )


def truncate_text(value: str, limit_chars: int) -> tuple[str, bool]:
    if limit_chars < 0:
        raise ValidationError("local_worker.executor", "Output limit cannot be negative")
    if len(value) <= limit_chars:
        return value, False
    suffix = "\n[TRUNCATED]"
    if limit_chars <= len(suffix):
        return value[:limit_chars], True
    return value[: limit_chars - len(suffix)] + suffix, True


def first_unsafe_live_arg(args: tuple[str, ...]) -> str | None:
    for arg in args:
        if UNSAFE_LIVE_ARG_RE.search(arg):
            return arg
    return None


def build_live_readonly_process_args(proposal: CommandProposal) -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        proposal.command.strip(),
        *proposal.args,
    ]


def command_fingerprint(proposal: CommandProposal) -> str:
    return compute_plan_hash(
        {
            "command": proposal.command.strip(),
            "args": list(proposal.args),
            "cwd": proposal.cwd,
            "expected_risk": proposal.expected_risk.value,
        }
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
