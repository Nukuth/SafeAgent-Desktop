from pathlib import Path

from safeagent.shared.module_boundaries import check_module_boundaries, format_boundary_report


def test_current_module_boundaries_are_valid():
    violations = check_module_boundaries(Path("."))
    assert violations == [], format_boundary_report(violations)


def test_module_boundary_checker_rejects_shared_to_worker_import(tmp_path):
    write_package(tmp_path, "src/safeagent/shared/bad.py", "from safeagent.local_worker.policy import PolicyEngine\n")
    violations = check_module_boundaries(tmp_path)
    assert len(violations) == 1
    assert violations[0].module == "safeagent.shared.bad"
    assert violations[0].forbidden_import == "safeagent.local_worker.policy"


def test_module_boundary_checker_rejects_worker_to_server_import(tmp_path):
    write_package(tmp_path, "src/safeagent/local_worker/bad.py", "import safeagent.server.db\n")
    violations = check_module_boundaries(tmp_path)
    assert len(violations) == 1
    assert violations[0].module == "safeagent.local_worker.bad"
    assert violations[0].forbidden_import == "safeagent.server.db"


def test_module_boundary_checker_rejects_server_to_worker_import(tmp_path):
    write_package(tmp_path, "src/safeagent/server/bad.py", "from safeagent.local_worker import worker\n")
    violations = check_module_boundaries(tmp_path)
    assert len(violations) == 1
    assert violations[0].module == "safeagent.server.bad"
    assert violations[0].forbidden_import == "safeagent.local_worker"


def test_module_boundary_report_is_actionable(tmp_path):
    write_package(tmp_path, "src/safeagent/server/bad.py", "import safeagent.local_worker.worker\n")
    report = format_boundary_report(check_module_boundaries(tmp_path))
    assert "FAIL module boundaries" in report
    assert "src" in report
    assert "module-boundary" in report


def write_package(root: Path, file_path: str, content: str) -> None:
    path = root / file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    current = root / "src"
    for part in ("safeagent", *Path(file_path).parts[2:-1]):
        current = current / part
        init = current / "__init__.py"
        init.parent.mkdir(parents=True, exist_ok=True)
        init.write_text("", encoding="utf-8")
    path.write_text(content, encoding="utf-8")
