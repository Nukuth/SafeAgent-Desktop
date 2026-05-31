from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_plan_hash(plan: dict[str, Any]) -> str:
    """Create a stable hash for the exact plan that an approval covers."""

    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

