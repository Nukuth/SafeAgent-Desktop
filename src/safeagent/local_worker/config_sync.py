from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from safeagent.shared.errors import ValidationError


def canonical_config(value: Any) -> Any:
    """Normalize config values for YAML/JSON semantic comparison."""

    if isinstance(value, dict):
        return {str(key): canonical_config(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [canonical_config(item) for item in value]
    return value


def compare_config_pairs(pairs: list[tuple[Path, Path]]) -> list[dict[str, str]]:
    mismatches: list[dict[str, str]] = []
    for yaml_path, json_path in pairs:
        yaml_config = canonical_config(load_yaml_config(yaml_path))
        json_config = canonical_config(load_json_config(json_path))
        if yaml_config != json_config:
            mismatches.append({"yaml": str(yaml_path), "json": str(json_path)})
    return mismatches


def load_json_config(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError("local_worker.config_sync", f"JSON config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(
            "local_worker.config_sync",
            f"JSON config is invalid: {path}",
            {"error": str(exc)},
        ) from exc


def load_yaml_config(path: Path) -> Any:
    text: str
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValidationError("local_worker.config_sync", f"YAML config not found: {path}") from exc
    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError as exc:
        try:
            return parse_yaml_subset(text)
        except Exception as parse_exc:
            raise ValidationError(
                "local_worker.config_sync",
                "PyYAML is not installed and fallback YAML parser could not parse config",
                {"install": "python -m pip install -e .[dev]", "error": str(parse_exc)},
            ) from exc
    except Exception as exc:
        raise ValidationError(
            "local_worker.config_sync",
            f"YAML config is invalid: {path}",
            {"error": str(exc)},
        ) from exc
    return yaml.safe_load(text)


def parse_yaml_subset(text: str) -> Any:
    """Parse the small YAML subset used by configs/*.yaml.

    This fallback intentionally supports only nested mappings, scalar lists,
    empty lists, booleans, and inline one-level maps like
    `{from: planner, to: shell_agent}`.
    """

    lines = [
        line.rstrip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not lines:
        return {}
    value, index = _parse_yaml_mapping(lines, 0, _line_indent(lines[0]))
    if index != len(lines):
        raise ValueError(f"unexpected trailing YAML at line {index + 1}")
    return value


def _parse_yaml_mapping(lines: list[str], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        current_indent = _line_indent(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"unexpected indent at line {index + 1}")
        stripped = line.strip()
        if stripped.startswith("- "):
            break
        key, raw_value = _split_yaml_key_value(stripped, index)
        if raw_value == "":
            if index + 1 >= len(lines) or _line_indent(lines[index + 1]) <= indent:
                result[key] = {}
                index += 1
                continue
            child_indent = _line_indent(lines[index + 1])
            if lines[index + 1].strip().startswith("- "):
                child, index = _parse_yaml_list(lines, index + 1, child_indent)
            else:
                child, index = _parse_yaml_mapping(lines, index + 1, child_indent)
            result[key] = child
        else:
            result[key] = _parse_yaml_scalar(raw_value)
            index += 1
    return result, index


def _parse_yaml_list(lines: list[str], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line = lines[index]
        current_indent = _line_indent(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"unexpected list indent at line {index + 1}")
        stripped = line.strip()
        if not stripped.startswith("- "):
            break
        raw_value = stripped[2:].strip()
        result.append(_parse_yaml_scalar(raw_value))
        index += 1
    return result, index


def _split_yaml_key_value(stripped: str, index: int) -> tuple[str, str]:
    if ":" not in stripped:
        raise ValueError(f"expected key/value at line {index + 1}")
    key, raw_value = stripped.split(":", 1)
    return key.strip(), raw_value.strip()


def _parse_yaml_scalar(raw: str) -> Any:
    if raw == "[]":
        return []
    if raw == "{}":
        return {}
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.startswith("{") and raw.endswith("}"):
        return _parse_inline_map(raw)
    return raw.strip('"').strip("'")


def _parse_inline_map(raw: str) -> dict[str, Any]:
    inner = raw[1:-1].strip()
    if not inner:
        return {}
    result: dict[str, Any] = {}
    for part in inner.split(","):
        key, value = part.split(":", 1)
        result[key.strip()] = _parse_yaml_scalar(value.strip())
    return result


def _line_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
