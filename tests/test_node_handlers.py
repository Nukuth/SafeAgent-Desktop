from pathlib import Path

from safeagent.local_worker.graph_plan import GraphPlanCompiler
from safeagent.local_worker.graph_runner import GraphRunner, GraphState
from safeagent.local_worker.node_handlers import build_default_handlers
from safeagent.local_worker.providers import ModelRequest, ModelResponse, ProviderRegistry
from safeagent.local_worker.registry import load_default_registries
from safeagent.shared.errors import ValidationError


class FakeProvider:
    def __init__(self, content: str | None = None) -> None:
        self.requests: list[ModelRequest] = []
        self.content = content

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(
            model=request.model,
            content=self.content or f"fake response for {request.purpose}",
            input_tokens=3,
            output_tokens=5,
            cost_estimate=0.01,
        )


class FailingProvider:
    def generate(self, request: ModelRequest) -> ModelResponse:
        raise ValidationError(
            "test.provider",
            "provider failed with token sk-abcdefghijklmnopqrstuvwxyz",
            {"api_key": "sk-abcdefghijklmnopqrstuvwxyz", "node": request.purpose},
        )


def test_default_handlers_cover_all_configured_agents():
    agents, _profiles = load_default_registries(Path("configs"))
    handlers = build_default_handlers()
    missing = sorted(agents.ids - set(handlers))
    assert missing == []


def test_default_handlers_produce_structured_outputs():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    result = GraphRunner(build_default_handlers()).run(
        graph,
        GraphState(task_id="task_1", run_id="run_1", payload={"content": "查看状态", "profile": "safe_shell"}),
    )
    assert result.status == "completed"
    outputs = {item.node_id: item.output for item in result.node_results}
    assert outputs["planner"]["selected_profile"] == "safe_shell"
    assert outputs["executor"]["execution_status"] == "not_executed"
    assert outputs["summarizer"]["summary"] == "placeholder graph summary"


def test_model_enabled_handler_records_model_output_without_tool_execution():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    provider = FakeProvider()
    result = GraphRunner(build_default_handlers(ProviderRegistry({"deepseek": provider}))).run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={
                "content": "inspect workspace",
                "profile": "safe_shell",
                "model_route": {"primary_model": "deepseek", "review_model": None},
            },
        ),
    )
    assert result.status == "completed"
    outputs = {item.node_id: item.output for item in result.node_results}
    assert outputs["planner"]["model"]["model_status"] == "completed"
    assert outputs["planner"]["model"]["content"] == "fake response for planning"
    assert outputs["executor"]["execution_status"] == "not_executed"
    assert provider.requests[0].purpose == "planning"


def test_successful_model_output_is_redacted():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    provider = FakeProvider("model echoed sk-abcdefghijklmnopqrstuvwxyz")
    result = GraphRunner(build_default_handlers(ProviderRegistry({"deepseek": provider}))).run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={
                "content": "inspect workspace",
                "profile": "safe_shell",
                "model_route": {"primary_model": "deepseek", "review_model": None},
            },
        ),
    )
    assert result.status == "completed"
    serialized = str(result.to_dict())
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in serialized
    assert "model echoed [REDACTED]" in serialized


def test_unconfigured_provider_is_isolated_to_node_output():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    result = GraphRunner(build_default_handlers(ProviderRegistry())).run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={
                "content": "inspect workspace",
                "profile": "safe_shell",
                "model_route": {"primary_model": "deepseek", "review_model": None},
            },
        ),
    )
    assert result.status == "completed"
    outputs = {item.node_id: item.output for item in result.node_results}
    assert outputs["planner"]["model"]["model_status"] == "unavailable"
    assert outputs["planner"]["model"]["error"]["code"] == "provider.not_configured"


def test_provider_errors_are_redacted_and_do_not_fail_graph():
    agents, profiles = load_default_registries(Path("configs"))
    graph = GraphPlanCompiler(agents).compile(profiles.get("safe_shell"))
    result = GraphRunner(build_default_handlers(ProviderRegistry({"deepseek": FailingProvider()}))).run(
        graph,
        GraphState(
            task_id="task_1",
            run_id="run_1",
            payload={
                "content": "inspect workspace",
                "profile": "safe_shell",
                "model_route": {"primary_model": "deepseek", "review_model": None},
            },
        ),
    )
    assert result.status == "completed"
    serialized = str(result.to_dict())
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in serialized
    assert "[REDACTED]" in serialized
