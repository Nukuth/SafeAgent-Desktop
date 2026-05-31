from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.shared.error_catalog import ERROR_CATALOG, find_unregistered_error_codes  # noqa: E402


def main() -> int:
    unknown = find_unregistered_error_codes(SRC)
    if unknown:
        print("FAIL unregistered error codes", file=sys.stderr)
        for code, locations in unknown.items():
            print(f"- {code}", file=sys.stderr)
            for location in locations:
                print(f"  {location}", file=sys.stderr)
        return 1
    print("OK error catalog")
    print(f"registered_codes={len(ERROR_CATALOG)}")
    for code in sorted(ERROR_CATALOG):
        print(f"- {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
