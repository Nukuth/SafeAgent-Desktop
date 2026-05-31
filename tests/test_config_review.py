import json
from pathlib import Path

from safeagent.local_worker.config_review import review_config_directory


def test_current_config_permission_review_has_no_blocking_findings():
    report = review_config_directory(Path("configs"))

    assert report.blocking_count == 0
    codes = {finding.code for finding in report.findings}
    assert "agent.executor_boundary" in codes
    assert "profile.remote_executor" in codes
    assert "model.codex_disabled" in codes
    assert len(report.config_hash) == 64


def test_config_permission_review_blocks_remote_default_api_keys(tmp_path):
    copy_config_dir(tmp_path)
    models_path = tmp_path / "models.json"
    data = json.loads(models_path.read_text(encoding="utf-8"))
    data["providers"]["deepseek"]["default_api_key"] = "placeholder-key"
    models_path.write_text(json.dumps(data), encoding="utf-8")

    report = review_config_directory(tmp_path)

    assert report.blocking_count >= 1
    finding = next(item for item in report.findings if item.code == "model.default_api_key")
    assert finding.details["provider_id"] == "deepseek"


def test_config_permission_review_reports_yaml_json_mismatch(tmp_path):
    copy_config_dir(tmp_path)
    profiles_path = tmp_path / "profiles.json"
    data = json.loads(profiles_path.read_text(encoding="utf-8"))
    data["profiles"]["safe_shell"]["remote_allowed"] = False
    profiles_path.write_text(json.dumps(data), encoding="utf-8")

    report = review_config_directory(tmp_path)

    assert report.blocking_count >= 1
    assert any(finding.code == "config.yaml_json_mismatch" for finding in report.findings)


def test_config_permission_review_reports_invalid_json_without_crashing(tmp_path):
    copy_config_dir(tmp_path)
    (tmp_path / "agents.json").write_text("{invalid", encoding="utf-8")

    report = review_config_directory(tmp_path)

    assert report.blocking_count >= 1
    assert any(finding.code == "config.validation_failed" for finding in report.findings)
    assert len(report.config_hash) == 64


def copy_config_dir(target: Path) -> None:
    source = Path("configs")
    for name in ("agents.json", "agents.yaml", "profiles.json", "profiles.yaml", "models.json", "models.yaml"):
        (target / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
