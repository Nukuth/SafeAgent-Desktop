from __future__ import annotations

import json
from pathlib import Path

from safeagent.shared.redaction import redact_payload
from safeagent.shared.time import utc_now_iso


def create_codex_review_package(
    *,
    reviews_dir: Path,
    task_id: str,
    run_id: str,
    node_id: str,
    prompt: str,
    model_error: dict[str, object] | None = None,
) -> dict[str, object]:
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_id = _safe_review_id(task_id, run_id, node_id)
    json_path = reviews_dir / f"{review_id}.json"
    markdown_path = reviews_dir / f"{review_id}.md"
    payload = redact_payload(
        {
            "review_id": review_id,
            "status": "manual_review_required",
            "task_id": task_id,
            "run_id": run_id,
            "node_id": node_id,
            "created_at": utc_now_iso(),
            "prompt": prompt,
            "model_error": model_error or {},
            "expected_response": {
                "recommendation": "approve | reject | revise",
                "risk_points": ["..."],
                "safer_alternative": "...",
                "requires_backup": True,
                "requires_human_confirmation": True,
                "notes": "...",
            },
        }
    )
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_markdown_for_payload(payload), encoding="utf-8")
    return {
        "review_id": review_id,
        "status": "manual_review_required",
        "markdown_path": str(markdown_path),
        "json_path": str(json_path),
        "instructions": (
            "Open the markdown review package, paste it into Codex for review, "
            "then paste the structured result back before local approval."
        ),
    }


def _safe_review_id(task_id: str, run_id: str, node_id: str) -> str:
    raw = f"review_{task_id}_{run_id}_{node_id}"
    return "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in raw)


def _markdown_for_payload(payload: dict[str, object]) -> str:
    return (
        "# SafeAgent Codex Manual Review Package\n\n"
        "Paste this review package into Codex. Do not approve execution directly; "
        "return a structured review that SafeAgent can record before local human confirmation.\n\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```\n"
    )
