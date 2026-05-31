from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.shared.module_boundaries import check_module_boundaries, format_boundary_report  # noqa: E402


def main() -> int:
    violations = check_module_boundaries(ROOT)
    print(format_boundary_report(violations))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
