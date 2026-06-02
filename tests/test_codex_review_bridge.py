from pathlib import Path

from safeagent.local_worker.codex_review_bridge import create_codex_review_package


def test_codex_review_package_writes_redacted_markdown_and_json(tmp_path):
    package = create_codex_review_package(
        reviews_dir=tmp_path / "reviews",
        task_id="task_1",
        run_id="run_1",
        node_id="codex_reviewer",
        prompt="Review command with key sk-abcdefghijklmnopqrstuvwxyz",
        model_error={
            "code": "provider.not_configured",
            "details": {"api_key": "sk-abcdefghijklmnopqrstuvwxyz"},
        },
    )

    markdown = Path(package["markdown_path"]).read_text(encoding="utf-8")
    payload = Path(package["json_path"]).read_text(encoding="utf-8")

    assert package["status"] == "manual_review_required"
    assert "task_1" in package["review_id"]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in markdown
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in payload
    assert "provider.not_configured" in payload
    assert "Paste this review package into Codex" in markdown
    assert package["instructions"].startswith("Open the markdown review package")
