from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change.*",
)

from safeagent.local_worker.graph_plan import GraphPlanCompiler  # noqa: E402
from safeagent.local_worker.graph_runtime import (  # noqa: E402
    build_graph_runner,
    parse_graph_runtime,
    resolved_graph_runtime_name,
)
from safeagent.local_worker.graph_runner import GraphState  # noqa: E402
from safeagent.local_worker.registry import load_default_registries  # noqa: E402
from safeagent.shared.enums import RiskLevel  # noqa: E402
from safeagent.shared.errors import SafeAgentError  # noqa: E402


def main() -> int:
    try:
        requested_runtime = parse_graph_runtime(os.environ.get("SAFEAGENT_GRAPH_RUNTIME", "auto"))
        resolved_runtime = resolved_graph_runtime_name(requested_runtime)
        agents, profiles = load_default_registries(ROOT / "configs")
        graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
        runner = build_graph_runner(requested_runtime, {})
        result = runner.run(
            graph,
            GraphState(
                task_id="task_runtime_check",
                run_id="run_runtime_check",
                payload={"policy": {"risk_level": RiskLevel.LOW.value}},
            ),
        )
    except SafeAgentError as exc:
        print(f"FAIL {exc.envelope.code}: {exc.envelope.message}", file=sys.stderr)
        if exc.envelope.details:
            print(exc.envelope.details, file=sys.stderr)
        return 1
    if result.status != "completed":
        print(f"FAIL graph runtime returned status={result.status}", file=sys.stderr)
        return 1
    node_ids = [item.node_id for item in result.node_results]
    expected = ["planner", "shell_agent", "rule_reviewer", "executor", "summarizer"]
    if node_ids != expected:
        print(f"FAIL graph runtime node path mismatch: {node_ids}", file=sys.stderr)
        return 1
    print("OK graph runtime")
    print(f"requested_runtime={requested_runtime.value}")
    print(f"resolved_runtime={resolved_runtime}")
    print(f"node_path={','.join(node_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
