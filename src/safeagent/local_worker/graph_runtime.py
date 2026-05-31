from __future__ import annotations

from enum import StrEnum

from safeagent.local_worker.graph_runner import GraphRunner, NodeHandler
from safeagent.local_worker.langgraph_adapter import LangGraphRunner, langgraph_available
from safeagent.shared.errors import DependencyMissingError, ValidationError


class GraphRuntime(StrEnum):
    LANGGRAPH = "langgraph"
    STDLIB = "stdlib"
    AUTO = "auto"


def parse_graph_runtime(raw: str | None) -> GraphRuntime:
    value = (raw or GraphRuntime.AUTO.value).strip().lower()
    try:
        return GraphRuntime(value)
    except ValueError as exc:
        raise ValidationError(
            "local_worker.graph_runtime",
            f"Unknown graph runtime: {raw}",
            {
                "value": raw,
                "allowed": [item.value for item in GraphRuntime],
            },
        ) from exc


def build_graph_runner(runtime: GraphRuntime, handlers: dict[str, NodeHandler]):
    if runtime == GraphRuntime.LANGGRAPH:
        if not langgraph_available():
            raise DependencyMissingError(
                "local_worker.graph_runtime",
                "langgraph",
                "Install project dependencies with .\\.venv\\Scripts\\python.exe -m pip install -e '.[dev]'",
            )
        return LangGraphRunner(handlers)
    if runtime == GraphRuntime.STDLIB:
        return GraphRunner(handlers)
    if runtime == GraphRuntime.AUTO:
        if langgraph_available():
            return LangGraphRunner(handlers)
        return GraphRunner(handlers)
    raise ValidationError(
        "local_worker.graph_runtime",
        f"Unsupported graph runtime: {runtime}",
        {"runtime": str(runtime)},
    )


def resolved_graph_runtime_name(runtime: GraphRuntime) -> str:
    if runtime == GraphRuntime.AUTO:
        return GraphRuntime.LANGGRAPH.value if langgraph_available() else GraphRuntime.STDLIB.value
    return runtime.value
