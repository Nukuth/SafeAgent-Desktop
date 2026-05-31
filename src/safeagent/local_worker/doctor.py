from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DoctorCheckResult:
    name: str
    return_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def passed(self) -> bool:
        return self.return_code == 0

    def summary_line(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"{status} {self.name}"


def doctor_exit_code(results: list[DoctorCheckResult]) -> int:
    return 0 if all(result.passed for result in results) else 1


def format_doctor_report(results: list[DoctorCheckResult]) -> str:
    lines: list[str] = []
    for result in results:
        lines.append(result.summary_line())
        if result.stdout.strip():
            lines.append(indent_block("stdout", result.stdout))
        stderr = filter_known_stderr(result.stderr)
        if stderr.strip():
            lines.append(indent_block("stderr", stderr))
    lines.append("OK doctor checks" if doctor_exit_code(results) == 0 else "FAIL doctor checks")
    return "\n".join(lines)


def indent_block(label: str, text: str) -> str:
    indented = "\n".join(f"  {line}" for line in text.rstrip().splitlines())
    return f"{label}:\n{indented}"


def filter_known_stderr(stderr: str) -> str:
    lines = stderr.splitlines()
    filtered: list[str] = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            continue
        if (
            "LangChainPendingDeprecationWarning" in line
            and "allowed_objects" in line
        ):
            skip_next = True
            continue
        filtered.append(line)
    return "\n".join(filtered)
