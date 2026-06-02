from pathlib import Path

from safeagent.local_worker.chat import run_local_agent_chat
from safeagent.local_worker.providers import ModelRequest, ModelResponse, ProviderRegistry
from safeagent.local_worker.settings import WorkerSettings


class FakeProvider:
    def __init__(self, content: str = "hello from fake agent") -> None:
        self.requests: list[ModelRequest] = []
        self.content = content

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(model=request.model, content=self.content, input_tokens=1, output_tokens=2)


def test_local_agent_chat_returns_model_content_when_provider_is_available():
    provider = FakeProvider("agent can talk")
    result = run_local_agent_chat(
        "hello",
        settings=_test_settings(),
        provider_registry=ProviderRegistry({"deepseek": provider}),
    )

    assert result.status == "completed"
    assert result.reply == "agent can talk"
    assert result.model_status == "completed"
    assert result.model == "deepseek"
    assert provider.requests


def test_local_agent_chat_reports_provider_error_without_crashing():
    result = run_local_agent_chat(
        "hello",
        settings=_test_settings(),
        provider_registry=ProviderRegistry(),
    )

    assert result.status == "completed"
    assert result.model_status == "unavailable"
    assert result.error is not None
    assert result.error["code"] == "provider.not_configured"
    assert "模型暂时没有可用回复" in result.reply


def test_local_agent_chat_blocks_high_risk_task_without_execution():
    result = run_local_agent_chat(
        "run diskpart and format the system disk",
        settings=_test_settings(),
        provider_registry=ProviderRegistry({"deepseek": FakeProvider()}),
    )

    assert result.status == "blocked"
    assert result.risk_level in {"high", "extreme"}
    assert result.execution_status == "not_executed"
    assert "阻止" in result.reply


def _test_settings() -> WorkerSettings:
    return WorkerSettings(
        control_url="http://127.0.0.1:8080",
        token="test-token",
        device_id="test-device",
        workspace_root=Path("E:/agents"),
        provider_env={},
    )
