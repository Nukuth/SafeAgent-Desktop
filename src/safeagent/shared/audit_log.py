from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any

from safeagent.shared.redaction import redact_payload


class JsonlAuditLog:
    """Append-only JSONL audit log with redaction at write time."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict[str, Any]) -> None:
        payload = redact_payload(event)
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line + "\n")

