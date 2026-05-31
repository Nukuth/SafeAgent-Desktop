from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkerSettings:
    control_url: str
    token: str
    device_id: str
    workspace_root: Path
    poll_interval_seconds: float = 5.0
    emergency_local_model: bool = False
    execution_mode: str = "dry_run"
    execution_timeout_seconds: float = 30.0
    stdout_limit_chars: int = 4000
    stderr_limit_chars: int = 4000
    enable_live_readonly: bool = False
    graph_runtime: str = "auto"

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        return cls(
            control_url=os.environ.get("SAFEAGENT_CONTROL_URL", "http://127.0.0.1:8080").rstrip("/"),
            token=os.environ.get("SAFEAGENT_WORKER_TOKEN", os.environ.get("SAFEAGENT_SERVER_TOKEN", "")),
            device_id=os.environ.get("SAFEAGENT_DEVICE_ID", "local-pc-1"),
            workspace_root=Path(os.environ.get("SAFEAGENT_WORKSPACE_ROOT", r"E:\agents")),
            poll_interval_seconds=float(os.environ.get("SAFEAGENT_POLL_INTERVAL_SECONDS", "5")),
            emergency_local_model=os.environ.get("SAFEAGENT_EMERGENCY_LOCAL_MODEL", "false").lower()
            in {"1", "true", "yes", "on"},
            execution_mode=os.environ.get("SAFEAGENT_EXECUTION_MODE", "dry_run"),
            execution_timeout_seconds=float(os.environ.get("SAFEAGENT_EXECUTION_TIMEOUT_SECONDS", "30")),
            stdout_limit_chars=int(os.environ.get("SAFEAGENT_STDOUT_LIMIT_CHARS", "4000")),
            stderr_limit_chars=int(os.environ.get("SAFEAGENT_STDERR_LIMIT_CHARS", "4000")),
            enable_live_readonly=os.environ.get("SAFEAGENT_ENABLE_LIVE_READONLY", "false").lower()
            in {"1", "true", "yes", "on"},
            graph_runtime=os.environ.get("SAFEAGENT_GRAPH_RUNTIME", "auto"),
        )

    @property
    def logs_dir(self) -> Path:
        return self.workspace_root / "logs"

    @property
    def downloads_dir(self) -> Path:
        return self.workspace_root / "downloads"

    @property
    def config_dir(self) -> Path:
        return self.workspace_root / "configs"
