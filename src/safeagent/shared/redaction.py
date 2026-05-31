from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SECRET_KEY_RE = re.compile(r"(api[_-]?key|token|secret|password|cookie|authorization)", re.I)
SECRET_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|Bearer\s+[A-Za-z0-9._-]{12,}|[A-Za-z0-9_-]{32,})"
)


def redact_text(value: str) -> str:
    return SECRET_VALUE_RE.sub("[REDACTED]", value)


def redact_payload(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_payload(item) for item in value)
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if SECRET_KEY_RE.search(key_text):
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = redact_payload(item)
        return redacted
    return value

