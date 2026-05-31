from dataclasses import dataclass
import os
import subprocess
import sys

from safeagent.local_worker.graph_runtime import (
    build_graph_runner,
    GraphRuntime,
    parse_graph_runtime,
    resolved_graph_runtime_name,
)
from safeagent.local_worker.graph_runner import GraphRunner
from safeagent.local_worker.langgraph_adapter import LangGraphRunner, langgraph_available
from safeagent.shared.errors import ValidationError


@dataclass(frozen=True, slots=True)
class ScriptResult:
    return_code: int
    stdout: str
    stderr: str


def run_script(args: list[str], env: dict[str, str] | None = None) -> ScriptResult:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    completed = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        shell=False,
        env=merged_env,
    )
    return ScriptResult(completed.returncode, completed.stdout, completed.stderr)


def test_parse_graph_runtime_defaults_to_auto():
    assert parse_graph_runtime(None) == GraphRuntime.AUTO
    assert parse_graph_runtime("") == GraphRuntime.AUTO
    assert parse_graph_runtime("LangGraph") == GraphRuntime.LANGGRAPH


def test_parse_graph_runtime_rejects_unknown_value():
    try:
        parse_graph_runtime("unsafe")
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert exc.envelope.details["allowed"] == ["langgraph", "stdlib", "auto"]
    else:
        raise AssertionError("expected ValidationError")


def test_build_graph_runner_resolves_runtime():
    stdlib = build_graph_runner(GraphRuntime.STDLIB, {})
    assert isinstance(stdlib, GraphRunner)
    auto = build_graph_runner(GraphRuntime.AUTO, {})
    if langgraph_available():
        assert isinstance(auto, LangGraphRunner)
        assert resolved_graph_runtime_name(GraphRuntime.AUTO) == "langgraph"
    else:
        assert isinstance(auto, GraphRunner)
        assert resolved_graph_runtime_name(GraphRuntime.AUTO) == "stdlib"


def test_graph_runtime_check_script_passes():
    result = run_script(["scripts/check_graph_runtime.py"])
    assert result.return_code == 0
    assert "OK graph runtime" in result.stdout
    assert "requested_runtime=auto" in result.stdout
    assert "node_path=planner,shell_agent,rule_reviewer,executor,summarizer" in result.stdout


def test_graph_runtime_check_script_reports_invalid_runtime():
    result = run_script(
        ["scripts/check_graph_runtime.py"],
        env={"SAFEAGENT_GRAPH_RUNTIME": "unsafe"},
    )
    assert result.return_code == 1
    assert "validation.failed" in result.stderr
    assert "Unknown graph runtime" in result.stderr
