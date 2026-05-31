from pathlib import Path

from safeagent.local_worker.config_sync import (
    canonical_config,
    load_json_config,
    load_yaml_config,
    parse_yaml_subset,
)
from safeagent.shared.errors import ValidationError


def test_canonical_config_sorts_dict_keys_without_changing_lists():
    left = canonical_config({"b": 2, "a": [{"d": 4, "c": 3}]})
    right = canonical_config({"a": [{"c": 3, "d": 4}], "b": 2})
    assert left == right
    assert list(left) == ["a", "b"]


def test_load_json_config_reports_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad", encoding="utf-8")
    try:
        load_json_config(path)
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert "invalid" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")


def test_load_yaml_config_reports_missing_pyyaml_or_missing_file(tmp_path):
    path = tmp_path / "missing.yaml"
    try:
        load_yaml_config(path)
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert "not found" in exc.envelope.message
    else:
        raise AssertionError("expected ValidationError")


def test_current_json_configs_are_valid():
    assert load_json_config(Path("configs/agents.json"))["agents"]
    assert load_json_config(Path("configs/profiles.json"))["profiles"]
    assert load_json_config(Path("configs/models.json"))["providers"]


def test_fallback_yaml_parser_handles_current_config_subset():
    parsed = parse_yaml_subset(
        """
root:
  enabled: true
  tools: []
  nodes:
    - planner
    - executor
  edges:
    - {from: planner, to: executor, condition: approved}
"""
    )
    assert parsed["root"]["enabled"] is True
    assert parsed["root"]["tools"] == []
    assert parsed["root"]["nodes"] == ["planner", "executor"]
    assert parsed["root"]["edges"][0]["condition"] == "approved"


def test_current_yaml_configs_parse_without_pyyaml():
    assert parse_yaml_subset(Path("configs/agents.yaml").read_text(encoding="utf-8"))["agents"]
    assert parse_yaml_subset(Path("configs/profiles.yaml").read_text(encoding="utf-8"))["profiles"]
    assert parse_yaml_subset(Path("configs/models.yaml").read_text(encoding="utf-8"))["providers"]
