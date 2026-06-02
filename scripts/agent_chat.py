from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.chat import run_local_agent_chat  # noqa: E402
from safeagent.shared.errors import SafeAgentError  # noqa: E402
from safeagent.shared.redaction import redact_payload  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local SafeAgent chat turn without starting the cloud server.")
    parser.add_argument("--message", help="Single message to send to the local agents.")
    parser.add_argument("--profile", help="Optional profile, such as safe_shell, file_organize, code_change, research.")
    parser.add_argument("--local", action="store_true", help="Route ordinary model calls to local_qwen.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable result.")
    args = parser.parse_args()

    if args.message:
        return _run_one(args.message, args.profile, args.local, args.json)
    print("SafeAgent local chat. Type exit to quit.")
    while True:
        try:
            message = input("you> ").strip()
        except EOFError:
            return 0
        if not message:
            continue
        if message.lower() in {"exit", "quit"}:
            return 0
        _run_one(message, args.profile, args.local, args.json)


def _run_one(message: str, profile: str | None, use_local: bool, as_json: bool) -> int:
    try:
        result = run_local_agent_chat(
            message,
            requested_profile=profile,
            emergency_local_model=True if use_local else None,
        )
    except SafeAgentError as exc:
        payload = {"error": redact_payload(exc.envelope.to_dict())}
        if as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"SafeAgent failed: {exc.envelope.code} {exc.envelope.message}")
            if exc.envelope.details:
                print(json.dumps(redact_payload(exc.envelope.details), ensure_ascii=False, sort_keys=True))
        return 1

    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"agent> {result.reply}")
        print(
            "status="
            f"{result.status} profile={result.profile} risk={result.risk_level} "
            f"model_status={result.model_status} model={result.model} execution={result.execution_status}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
