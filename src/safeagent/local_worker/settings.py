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
    local_qwen_base_url: str = "http://127.0.0.1:8000/v1"
    local_qwen_model: str = "qwen-35b-local"
    local_qwen_api_key: str = "local-no-key"
    model_timeout_seconds: float = 60.0
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    deepseek_api_key: str = ""
    codex_base_url: str = ""
    codex_model: str = "codex"
    codex_api_key: str = ""
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
            local_qwen_base_url=os.environ.get("SAFEAGENT_LOCAL_QWEN_BASE_URL", "http://127.0.0.1:8000/v1"),
            local_qwen_model=os.environ.get("SAFEAGENT_LOCAL_QWEN_MODEL", "qwen-35b-local"),
            local_qwen_api_key=os.environ.get("SAFEAGENT_LOCAL_QWEN_API_KEY", "local-no-key"),
            model_timeout_seconds=float(os.environ.get("SAFEAGENT_MODEL_TIMEOUT_SECONDS", "60")),
            deepseek_base_url=os.environ.get("SAFEAGENT_DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            deepseek_model=os.environ.get("SAFEAGENT_DEEPSEEK_MODEL", "deepseek-chat"),
            deepseek_api_key=os.environ.get("SAFEAGENT_DEEPSEEK_API_KEY", ""),
            codex_base_url=os.environ.get("SAFEAGENT_CODEX_BASE_URL", ""),
            codex_model=os.environ.get("SAFEAGENT_CODEX_MODEL", "codex"),
            codex_api_key=os.environ.get("SAFEAGENT_CODEX_API_KEY", ""),
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
