from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Mapping

from safeagent.shared.errors import ValidationError


def load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValidationError(
                "local_worker.env_file",
                "Environment file line must use KEY=VALUE",
                {"path": str(path), "line_number": line_number},
            )
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not _is_valid_env_key(key):
            raise ValidationError(
                "local_worker.env_file",
                "Environment file contains invalid key",
                {"path": str(path), "line_number": line_number},
            )
        values[key] = _strip_env_value(value.strip())
    return values


def build_effective_env(
    workspace_root: Path | None = None,
    base_env: Mapping[str, str] | None = None,
    env_file: Path | None = None,
) -> dict[str, str]:
    current_env = dict(os.environ if base_env is None else base_env)
    default_workspace = Path(current_env.get("SAFEAGENT_WORKSPACE_ROOT", r"E:\agents"))
    local_env_file = env_file or Path(current_env.get("SAFEAGENT_ENV_FILE", str((workspace_root or default_workspace) / ".env.local")))
    file_env = load_env_file(local_env_file)
    return {**file_env, **current_env}


def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _is_valid_env_key(key: str) -> bool:
    return all(char == "_" or char.isalnum() for char in key) and not key[0].isdigit()
