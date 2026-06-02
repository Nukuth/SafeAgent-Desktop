from pathlib import Path

from safeagent.local_worker.model_router import ModelRouter
from safeagent.local_worker.providers import (
    ModelRequest,
    NullProvider,
    OpenAIResponsesProvider,
    OpenAIResponsesProviderConfig,
    ProviderNotConfiguredError,
    build_provider_registry,
    build_provider_registry_from_config,
    load_model_provider_specs,
    model_provider_config_status,
)
from safeagent.shared.enums import RiskLevel
from safeagent.shared.errors import ValidationError


def test_model_router_uses_deepseek_default_for_low_risk():
    route = ModelRouter().route(model_policy="deepseek_default", risk_level=RiskLevel.LOW)
    assert route.primary_model == "deepseek"
    assert route.fallback_model == "codex"
    assert route.review_model is None


def test_model_router_escalates_high_risk_to_codex_review():
    route = ModelRouter().route(model_policy="deepseek_default", risk_level=RiskLevel.HIGH)
    assert route.primary_model == "deepseek"
    assert route.review_model == "codex"


def test_null_provider_fails_with_clear_error():
    try:
        NullProvider().generate(ModelRequest(model="deepseek", prompt="hello", purpose="test"))
    except ProviderNotConfiguredError as exc:
        assert exc.envelope.code == "provider.not_configured"
        assert exc.envelope.details["model"] == "deepseek"
    else:
        raise AssertionError("expected ProviderNotConfiguredError")


def test_model_router_routes_to_local_qwen_in_emergency_mode():
    route = ModelRouter().route(
        model_policy="deepseek_default",
        risk_level=RiskLevel.LOW,
        emergency_local=True,
    )
    assert route.primary_model == "local_qwen"
    assert route.review_model is None


def test_model_router_local_qwen_does_not_claim_high_risk_review():
    route = ModelRouter().route(
        model_policy="deepseek_default",
        risk_level=RiskLevel.HIGH,
        emergency_local=True,
    )
    assert route.primary_model == "local_qwen"
    assert "cannot approve" in route.reason


def test_provider_registry_builds_only_configured_remote_models():
    registry = build_provider_registry(
        local_qwen_base_url="http://127.0.0.1:8000/v1",
        local_qwen_model="qwen-35b-local",
        local_qwen_api_key="local-no-key",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_model="deepseek-chat",
        deepseek_api_key="",
        codex_base_url="",
        codex_model="codex",
        codex_api_key="",
        timeout_seconds=60,
    )
    status = registry.public_status()
    assert "local_qwen" in status
    assert "deepseek" not in status
    assert "codex" not in status
    assert status["local_qwen"]["model"] == "qwen-35b-local"


def test_direct_provider_registry_rejects_non_35b_32b_local_qwen():
    try:
        build_provider_registry(
            local_qwen_base_url="http://127.0.0.1:8000/v1",
            local_qwen_model="qwen3.5:27b",
            local_qwen_api_key="local-no-key",
            deepseek_base_url="",
            deepseek_model="deepseek-chat",
            deepseek_api_key="",
            codex_base_url="",
            codex_model="codex",
            codex_api_key="",
            timeout_seconds=60,
        )
    except ValidationError as exc:
        assert exc.envelope.details["provider_id"] == "local_qwen"
        assert exc.envelope.details["model"] == "qwen3.5:27b"
    else:
        raise AssertionError("expected ValidationError")


def test_model_provider_specs_load_from_config_without_secret_values():
    specs = load_model_provider_specs(Path("configs/models.json"))
    assert specs["deepseek"].api_key_env == "SAFEAGENT_DEEPSEEK_API_KEY"
    assert specs["deepseek"].default_api_key == ""
    assert specs["local_qwen"].model == "qwen-35b-local"


def test_provider_registry_uses_config_and_env_only_api_keys():
    registry = build_provider_registry_from_config(
        Path("configs/models.json"),
        env={
            "SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key",
            "SAFEAGENT_DEEPSEEK_API_KEY": "sk-test-not-real",
        },
    )
    status = registry.public_status()
    assert "local_qwen" in status
    assert "deepseek" in status
    assert "codex" not in status
    assert status["deepseek"]["has_api_key"] is True
    assert "sk-test-not-real" not in str(status)


def test_unconfigured_deepseek_provider_reports_missing_key_env():
    registry = build_provider_registry_from_config(
        Path("configs/models.json"),
        env={"SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key"},
    )

    try:
        registry.get("deepseek").generate(ModelRequest(model="deepseek", prompt="hello", purpose="test"))
    except ProviderNotConfiguredError as exc:
        assert exc.envelope.code == "provider.not_configured"
        assert "SAFEAGENT_DEEPSEEK_API_KEY" in exc.envelope.message
        assert exc.envelope.details["model"] == "deepseek"
        assert exc.envelope.details["api_key_env"] == "SAFEAGENT_DEEPSEEK_API_KEY"
        assert "SAFEAGENT_DEEPSEEK_API_KEY" in exc.envelope.details["reason"]
        assert "scripts/check_model_config.py" in exc.envelope.details["check_command"]
    else:
        raise AssertionError("expected ProviderNotConfiguredError")


def test_model_provider_config_status_does_not_expose_api_key():
    statuses = model_provider_config_status(
        Path("configs/models.json"),
        env={
            "SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key",
            "SAFEAGENT_DEEPSEEK_API_KEY": "sk-test-not-real",
            "SAFEAGENT_CODEX_API_KEY": "sk-test-codex-not-real",
        },
    )
    by_id = {item["provider_id"]: item for item in statuses}
    assert by_id["local_qwen"]["ready"] is True
    assert by_id["local_qwen"]["api_key_source"] == "env"
    assert by_id["deepseek"]["ready"] is True
    assert by_id["deepseek"]["api_key_env"] == "SAFEAGENT_DEEPSEEK_API_KEY"
    assert by_id["codex"]["ready"] is True
    assert by_id["codex"]["type"] == "openai_responses"
    assert by_id["codex"]["model"] == "gpt-5.5"
    assert "sk-test-not-real" not in str(statuses)
    assert "sk-test-codex-not-real" not in str(statuses)


def test_provider_registry_builds_codex_responses_provider_from_config():
    registry = build_provider_registry_from_config(
        Path("configs/models.json"),
        env={
            "SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key",
            "SAFEAGENT_DEEPSEEK_API_KEY": "sk-test-not-real",
            "SAFEAGENT_CODEX_API_KEY": "sk-test-codex-not-real",
        },
    )

    codex = registry.get("codex")

    assert isinstance(codex, OpenAIResponsesProvider)
    assert registry.public_status()["codex"]["model"] == "gpt-5.5"
    assert "sk-test-codex-not-real" not in str(registry.public_status())


def test_openai_responses_provider_posts_to_responses_api():
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return (
                b'{"output_text":"review ok",'
                b'"usage":{"input_tokens":11,"output_tokens":3}}'
            )

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["body"] = request.data.decode("utf-8")
        seen["timeout"] = timeout
        return FakeResponse()

    import safeagent.local_worker.providers as providers_module

    original_urlopen = providers_module.urlopen
    providers_module.urlopen = fake_urlopen
    provider = OpenAIResponsesProvider(
        OpenAIResponsesProviderConfig(
            provider_id="codex",
            base_url="https://api.openai.com/v1",
            api_key="sk-test-codex-not-real",
            model="gpt-5.5",
            timeout_seconds=12,
            system_prompt="Review only.",
        )
    )

    try:
        response = provider.generate(ModelRequest(model="codex", prompt="check this diff", purpose="review"))
    finally:
        providers_module.urlopen = original_urlopen

    assert response.content == "review ok"
    assert response.model == "gpt-5.5"
    assert response.input_tokens == 11
    assert response.output_tokens == 3
    assert seen["url"] == "https://api.openai.com/v1/responses"
    assert '"instructions": "Review only."' in seen["body"]
    assert '"input": "check this diff"' in seen["body"]


def test_codex_provider_without_key_reports_missing_key_env():
    registry = build_provider_registry_from_config(
        Path("configs/models.json"),
        env={
            "SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key",
            "SAFEAGENT_DEEPSEEK_API_KEY": "sk-test-not-real",
        },
    )

    try:
        registry.get("codex").generate(ModelRequest(model="codex", prompt="review", purpose="test"))
    except ProviderNotConfiguredError as exc:
        assert exc.envelope.code == "provider.not_configured"
        assert "SAFEAGENT_CODEX_API_KEY" in exc.envelope.message
        assert exc.envelope.details["api_key_env"] == "SAFEAGENT_CODEX_API_KEY"
    else:
        raise AssertionError("expected ProviderNotConfiguredError")


def test_deepseek_provider_posts_to_chat_completions_api():
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return (
                b'{"choices":[{"message":{"content":"plan ok"}}],'
                b'"usage":{"prompt_tokens":7,"completion_tokens":2}}'
            )

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["body"] = request.data.decode("utf-8")
        seen["timeout"] = timeout
        return FakeResponse()

    import safeagent.local_worker.providers as providers_module

    original_urlopen = providers_module.urlopen
    providers_module.urlopen = fake_urlopen
    registry = build_provider_registry_from_config(
        Path("configs/models.json"),
        env={
            "SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key",
            "SAFEAGENT_DEEPSEEK_API_KEY": "sk-test-not-real",
        },
    )
    try:
        response = registry.get("deepseek").generate(ModelRequest(model="deepseek", prompt="make a plan", purpose="test"))
    finally:
        providers_module.urlopen = original_urlopen

    assert response.content == "plan ok"
    assert response.model == "deepseek-chat"
    assert seen["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert '"model": "deepseek-chat"' in seen["body"]


def test_model_provider_config_status_accepts_env_file_values(tmp_path):
    from safeagent.local_worker.env_file import build_effective_env

    env_file = tmp_path / ".env.local"
    env_file.write_text("SAFEAGENT_DEEPSEEK_API_KEY=sk-test-not-real", encoding="utf-8")
    statuses = model_provider_config_status(
        Path("configs/models.json"),
        env=build_effective_env(base_env={}, env_file=env_file),
    )
    by_id = {item["provider_id"]: item for item in statuses}
    assert by_id["deepseek"]["ready"] is True
    assert by_id["deepseek"]["api_key_source"] == "env"
    assert "sk-test-not-real" not in str(statuses)


def test_local_qwen_status_accepts_32b_class_model_ids(tmp_path):
    config_path = tmp_path / "models.json"
    config_path.write_text(
        """
        {
          "providers": {
            "local_qwen": {
              "type": "openai_compatible",
              "enabled": true,
              "base_url": "http://127.0.0.1:8000/v1",
              "model": "Qwen2.5-Coder-32B-Instruct-GGUF:Q4_K_M",
              "api_key_env": "SAFEAGENT_LOCAL_QWEN_API_KEY",
              "default_api_key": "local-no-key",
              "timeout_seconds": "60"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    statuses = model_provider_config_status(config_path, env={})

    assert statuses[0]["ready"] is True
    assert statuses[0]["reason"] == "ready"


def test_local_qwen_status_rejects_non_35b_32b_model_ids(tmp_path):
    config_path = tmp_path / "models.json"
    config_path.write_text(
        """
        {
          "providers": {
            "local_qwen": {
              "type": "openai_compatible",
              "enabled": true,
              "base_url": "http://127.0.0.1:8000/v1",
              "model": "huihui_ai/qwen3.5-abliterated:4B",
              "api_key_env": "SAFEAGENT_LOCAL_QWEN_API_KEY",
              "default_api_key": "local-no-key",
              "timeout_seconds": "60"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    statuses = model_provider_config_status(config_path, env={})

    assert statuses[0]["ready"] is False
    assert "35B/32B" in statuses[0]["reason"]
    assert "4B" in statuses[0]["reason"]


def test_provider_registry_rejects_non_35b_32b_local_qwen(tmp_path):
    config_path = tmp_path / "models.json"
    config_path.write_text(
        """
        {
          "providers": {
            "local_qwen": {
              "type": "openai_compatible",
              "enabled": true,
              "base_url": "http://127.0.0.1:8000/v1",
              "model": "qwen3.5:27b",
              "api_key_env": "SAFEAGENT_LOCAL_QWEN_API_KEY",
              "default_api_key": "local-no-key",
              "timeout_seconds": "60"
            }
          }
        }
        """,
        encoding="utf-8",
    )

    try:
        build_provider_registry_from_config(config_path, env={})
    except ValidationError as exc:
        assert exc.envelope.code == "validation.failed"
        assert exc.envelope.details["provider_id"] == "local_qwen"
        assert exc.envelope.details["model"] == "qwen3.5:27b"
    else:
        raise AssertionError("expected ValidationError")
