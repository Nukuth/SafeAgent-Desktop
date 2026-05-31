from safeagent.local_worker.providers import (
    OpenAICompatibleLocalProvider,
    OpenAICompatibleProviderConfig,
)
from safeagent.shared.errors import TransientUpstreamError
from safeagent.local_worker.providers import ModelRequest


def test_local_provider_unreachable_endpoint_returns_structured_error():
    provider = OpenAICompatibleLocalProvider(
        OpenAICompatibleProviderConfig(
            provider_id="local_qwen",
            base_url="http://127.0.0.1:1/v1",
            api_key="local-no-key",
            model="qwen-35b-local",
            timeout_seconds=0.1,
        )
    )
    try:
        provider.generate(ModelRequest(model="local_qwen", prompt="hi", purpose="test"))
    except TransientUpstreamError as exc:
        assert exc.envelope.code == "upstream.transient"
        assert exc.envelope.retriable is True
    else:
        raise AssertionError("expected TransientUpstreamError")


def test_provider_public_status_does_not_expose_api_key():
    config = OpenAICompatibleProviderConfig(
        provider_id="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key="secret-value",
        model="deepseek-chat",
    )
    status = config.public_status()
    assert status["has_api_key"] is True
    assert "secret-value" not in str(status)
