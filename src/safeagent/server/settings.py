from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from safeagent.shared.env_file import build_effective_env


@dataclass(frozen=True, slots=True)
class ServerSettings:
    token: str
    worker_token: str
    db_path: Path

    @classmethod
    def from_env(cls) -> "ServerSettings":
        env = build_effective_env()
        token = env.get("SAFEAGENT_SERVER_TOKEN", "")
        return cls(
            token=token,
            worker_token=env.get("SAFEAGENT_WORKER_TOKEN", token),
            db_path=Path(env.get("SAFEAGENT_DB_PATH", r"E:\agents\state\server.sqlite3")),
        )
