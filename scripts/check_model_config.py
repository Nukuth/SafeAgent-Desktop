from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.providers import model_provider_config_status  # noqa: E402
from safeagent.shared.errors import SafeAgentError  # noqa: E402


def main() -> int:
    config_path = ROOT / "configs" / "models.json"
    try:
        statuses = model_provider_config_status(config_path)
    except SafeAgentError as exc:
        print(f"FAIL {exc.envelope.code}: {exc.envelope.message}", file=sys.stderr)
        if exc.envelope.details:
            print(exc.envelope.details, file=sys.stderr)
        return 1

    print("OK model config")
    for status in statuses:
        print(
            "provider={provider_id} enabled={enabled} ready={ready} "
            "model={model} base_url={base_url} api_key_env={api_key_env} "
            "has_api_key={has_api_key} api_key_source={api_key_source} reason={reason}".format(**status)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
