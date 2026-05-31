from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.config_sync import compare_config_pairs  # noqa: E402
from safeagent.local_worker.providers import load_model_provider_specs  # noqa: E402
from safeagent.local_worker.registry import load_default_registries  # noqa: E402
from safeagent.shared.errors import SafeAgentError  # noqa: E402


def main() -> int:
    config_dir = ROOT / "configs"
    pairs = [
        (config_dir / "agents.yaml", config_dir / "agents.json"),
        (config_dir / "profiles.yaml", config_dir / "profiles.json"),
        (config_dir / "models.yaml", config_dir / "models.json"),
    ]
    try:
        mismatches = compare_config_pairs(pairs)
        load_default_registries(config_dir)
        load_model_provider_specs(config_dir / "models.json")
    except SafeAgentError as exc:
        print(f"FAIL {exc.envelope.code}: {exc.envelope.message}", file=sys.stderr)
        if exc.envelope.details:
            print(exc.envelope.details, file=sys.stderr)
        return 1
    if mismatches:
        print("FAIL config YAML/JSON mismatch", file=sys.stderr)
        for item in mismatches:
            print(f"- {item['yaml']} != {item['json']}", file=sys.stderr)
        return 1
    print("OK config YAML/JSON sync and registry security contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
