from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.config_review import review_config_directory  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Review SafeAgent config permission and model-risk surfaces.")
    parser.add_argument("--config-dir", default=str(ROOT / "configs"), help="Config directory to review.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    report = review_config_directory(Path(args.config_dir))
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if report.blocking_count else 0
    else:
        print(f"config_dir={report.config_dir}")
        print(f"config_hash={report.config_hash}")
        print(f"blocking={report.blocking_count} warning={report.warning_count}")
        for finding in report.findings:
            print(f"{finding.severity.upper()} {finding.code}: {finding.message}")
            print(f"  path: {finding.path}")
            if finding.details:
                print(f"  details: {json.dumps(finding.details, ensure_ascii=False, sort_keys=True)}")
    if report.blocking_count:
        return 1
    print("OK config permission review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
