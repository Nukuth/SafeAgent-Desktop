from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from safeagent.local_worker.env_file import build_effective_env  # noqa: E402
from safeagent.local_worker.providers import (  # noqa: E402
    ModelRequest,
    build_provider_registry_from_config,
    model_provider_config_status,
)
from safeagent.shared.errors import SafeAgentError  # noqa: E402


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target not in {"all", "deepseek", "codex", "local_qwen"}:
        print("usage: python scripts/probe_model_providers.py [all|deepseek|codex|local_qwen]", file=sys.stderr)
        return 2

    config_path = ROOT / "configs" / "models.json"
    env = build_effective_env(ROOT)
    statuses = {item["provider_id"]: item for item in model_provider_config_status(config_path, env=env)}
    registry = build_provider_registry_from_config(config_path, env=env)
    targets = ["deepseek", "codex", "local_qwen"] if target == "all" else [target]

    exit_code = 0
    for provider_id in targets:
        status = statuses.get(provider_id)
        if status is None:
            print(f"FAIL {provider_id}: provider not found")
            exit_code = 1
            continue
        if not status["ready"]:
            print(
                "SKIP {provider_id}: ready=False reason={reason}".format(
                    provider_id=provider_id,
                    reason=status["reason"],
                )
            )
            exit_code = 1
            continue
        try:
            response = registry.get(provider_id).generate(
                ModelRequest(
                    model=provider_id,
                    prompt=(
                        "用一句中文回复："
                        f"{provider_id} provider 已完成连通测试。"
                    ),
                    purpose="connectivity_probe",
                )
            )
        except SafeAgentError as exc:
            print(f"FAIL {provider_id}: {exc.envelope.code} {exc.envelope.message}")
            exit_code = 1
            continue
        preview = response.content.replace("\r", " ").replace("\n", " ")[:160]
        print(
            "OK {provider_id}: model={model} input_tokens={input_tokens} "
            "output_tokens={output_tokens} reply={reply}".format(
                provider_id=provider_id,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                reply=preview,
            )
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
