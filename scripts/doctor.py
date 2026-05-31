from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.doctor import DoctorCheckResult, doctor_exit_code, format_doctor_report  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SafeAgent local health checks.")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip the full stdlib test suite; run config, smoke, and compile checks only.",
    )
    args = parser.parse_args()

    checks = [
        ("config_sync", [sys.executable, str(ROOT / "scripts" / "check_config_sync.py")]),
        ("config_permission_review", [sys.executable, str(ROOT / "scripts" / "review_config_permissions.py")]),
        ("model_config", [sys.executable, str(ROOT / "scripts" / "check_model_config.py")]),
        ("module_boundaries", [sys.executable, str(ROOT / "scripts" / "check_module_boundaries.py")]),
        ("error_catalog", [sys.executable, str(ROOT / "scripts" / "check_error_catalog.py")]),
        ("graph_runtime", [sys.executable, str(ROOT / "scripts" / "check_graph_runtime.py")]),
        ("local_smoke", [sys.executable, str(ROOT / "scripts" / "smoke_local_flow.py")]),
        ("compileall", [sys.executable, "-m", "compileall", "src", "scripts", "tests"]),
    ]
    if not args.quick:
        checks.append(("stdlib_tests", [sys.executable, str(ROOT / "scripts" / "run_stdlib_tests.py")]))

    results = [run_command(name, command) for name, command in checks]
    print(format_doctor_report(results))
    return doctor_exit_code(results)


def run_command(name: str, command: list[str]) -> DoctorCheckResult:
    env = os.environ.copy()
    warning_filter = "ignore:The default value of `allowed_objects` will change"
    existing_warnings = env.get("PYTHONWARNINGS")
    env["PYTHONWARNINGS"] = (
        f"{existing_warnings},{warning_filter}" if existing_warnings else warning_filter
    )
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        shell=False,
        env=env,
    )
    return DoctorCheckResult(
        name=name,
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


if __name__ == "__main__":
    raise SystemExit(main())
