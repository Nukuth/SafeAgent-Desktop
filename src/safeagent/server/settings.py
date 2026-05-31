from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ServerSettings:
    token: str
    worker_token: str
    db_path: Path

    @classmethod
    def from_env(cls) -> "ServerSettings":
        token = os.environ.get("SAFEAGENT_SERVER_TOKEN", "")
        return cls(
            token=token,
            worker_token=os.environ.get("SAFEAGENT_WORKER_TOKEN", token),
            db_path=Path(os.environ.get("SAFEAGENT_DB_PATH", r"E:\agents\state\server.sqlite3")),
        )
