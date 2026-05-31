from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ServerSettings:
    token: str
    db_path: Path

    @classmethod
    def from_env(cls) -> "ServerSettings":
        return cls(
            token=os.environ.get("SAFEAGENT_SERVER_TOKEN", ""),
            db_path=Path(os.environ.get("SAFEAGENT_DB_PATH", r"E:\agents\state\server.sqlite3")),
        )

