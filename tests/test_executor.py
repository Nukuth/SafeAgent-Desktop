from pathlib import Path

from safeagent.local_worker.executor import (
    CommandProposal,
    CommandValidator,
    DryRunExecutor,
    audit_execution_output,
    build_live_readonly_process_args,
    command_fingerprint,
    first_unsafe_live_arg,
    truncate_text,
)
from safeagent.local_worker.policy import PolicyEngine
from safeagent.shared.errors import PolicyDeniedError, ValidationError


def make_executor():
    policy = PolicyEngine(Path("E:/agents"))
    return DryRunExecutor(CommandValidator(Path("E:/agents"), policy))


def test_dry_run_executor_validates_readonly_command_without_execution():
    result = make_executor().execute(
        CommandProposal(command="Get-ChildItem", args=("E:\\agents",), cwd="E:\\agents")
    )
    assert result.executed is False
    assert result.exit_code is None
    assert result.validation.allowed is True
    assert "dry-run" in result.stderr
    assert result.timeout_seconds == 30.0
    assert result.output_audit.stderr_truncated is False
    assert result.validation.command_hash == command_fingerprint(
        CommandProposal(command="Get-ChildItem", args=("E:\\agents",), cwd="E:\\agents")
    )


def test_executor_denies_delete_command():
    try:
        make_executor().execute(CommandProposal(command="Remove-Item", args=("E:\\agents\\x",), cwd="E:\\agents"))
    except PolicyDeniedError as exc:
        assert exc.envelope.code == "policy.denied"
        assert exc.envelope.details["validation"]["allowed"] is False
    else:
        raise AssertionError("expected PolicyDeniedError")


def test_executor_denies_unknown_command():
    try:
        make_executor().execute(CommandProposal(command="python", args=("-c", "print(1)"), cwd="E:\\agents"))
    except PolicyDeniedError as exc:
        assert "not in read-only allowlist" in str(exc.envelope.details)
    else:
        raise AssertionError("expected PolicyDeniedError")


def test_command_fingerprint_changes_when_args_change():
    left = command_fingerprint(CommandProposal(command="Get-ChildItem", args=("E:\\agents",), cwd="E:\\agents"))
    right = command_fingerprint(CommandProposal(command="Get-ChildItem", args=("E:\\agents\\docs",), cwd="E:\\agents"))
    assert left != right


def test_unknown_live_execution_mode_is_denied():
    policy = PolicyEngine(Path("E:/agents"))
    executor = DryRunExecutor(CommandValidator(Path("E:/agents"), policy), execution_mode="live")
    try:
        executor.execute(CommandProposal(command="Get-ChildItem", args=("E:\\agents",), cwd="E:\\agents"))
    except PolicyDeniedError as exc:
        assert exc.envelope.details["validation"]["execution_mode"] == "live"
        assert "unsupported execution_mode" in str(exc.envelope.details)
    else:
        raise AssertionError("expected PolicyDeniedError")


def test_live_readonly_requires_explicit_enable_flag():
    policy = PolicyEngine(Path("E:/agents"))
    executor = DryRunExecutor(CommandValidator(Path("E:/agents"), policy), execution_mode="live_readonly")
    try:
        executor.execute(CommandProposal(command="Test-Path", args=("E:\\agents",), cwd="E:\\agents"))
    except PolicyDeniedError as exc:
        assert "SAFEAGENT_ENABLE_LIVE_READONLY" in str(exc.envelope.details)
    else:
        raise AssertionError("expected PolicyDeniedError")


def test_live_readonly_validation_allows_only_safe_subset_when_enabled():
    policy = PolicyEngine(Path("E:/agents"))
    validator = CommandValidator(Path("E:/agents"), policy, allow_live_readonly=True)
    allowed = validator.validate(
        CommandProposal(command="Test-Path", args=("E:\\agents",), cwd="E:\\agents"),
        execution_mode="live_readonly",
    )
    denied = validator.validate(
        CommandProposal(command="Get-Content", args=("E:\\agents\\README.md",), cwd="E:\\agents"),
        execution_mode="live_readonly",
    )
    assert allowed.allowed is True
    assert allowed.dry_run_only is False
    assert denied.allowed is False
    assert "live read-only allowlist" in str(denied.reasons)


def test_live_readonly_rejects_unsafe_argument_text():
    assert first_unsafe_live_arg(("E:\\agents; Remove-Item E:\\agents\\x",)) is not None
    policy = PolicyEngine(Path("E:/agents"))
    validator = CommandValidator(Path("E:/agents"), policy, allow_live_readonly=True)
    validation = validator.validate(
        CommandProposal(command="Test-Path", args=("E:\\agents; Remove-Item E:\\agents\\x",), cwd="E:\\agents"),
        execution_mode="live_readonly",
    )
    assert validation.allowed is False
    assert "unsafe" in str(validation.reasons)


def test_live_readonly_process_args_use_powershell_without_shell_string():
    args = build_live_readonly_process_args(CommandProposal(command="Test-Path", args=("E:\\agents",)))
    assert args[:6] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
    ]
    assert args[6:] == ["Test-Path", "E:\\agents"]


def test_audit_execution_output_redacts_and_truncates():
    stdout, stderr, audit = audit_execution_output(
        stdout="token sk-1234567890abcdefABCDEF",
        stderr="error line " * 10,
        stdout_limit_chars=100,
        stderr_limit_chars=20,
    )
    assert "sk-1234567890abcdefABCDEF" not in stdout
    assert "[REDACTED]" in stdout
    assert stderr.endswith("[TRUNCATED]")
    assert audit.stdout_truncated is False
    assert audit.stderr_truncated is True
    assert audit.stderr_limit_chars == 20


def test_truncate_text_rejects_negative_limit():
    try:
        truncate_text("hello", -1)
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
    else:
        raise AssertionError("expected ValidationError")
