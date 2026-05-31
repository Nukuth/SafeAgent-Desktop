from pathlib import Path

from safeagent.local_worker.model_router import ModelRouter
from safeagent.local_worker.providers import (
    ModelRequest,
    NullProvider,
    ProviderNotConfiguredError,
    build_provider_registry,
    build_provider_registry_from_config,
    load_model_provider_specs,
    model_provider_config_status,
)
from safeagent.shared.enums import RiskLevel


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


def test_model_provider_config_status_does_not_expose_api_key():
    statuses = model_provider_config_status(
        Path("configs/models.json"),
        env={
            "SAFEAGENT_LOCAL_QWEN_API_KEY": "local-no-key",
            "SAFEAGENT_DEEPSEEK_API_KEY": "sk-test-not-real",
        },
    )
    by_id = {item["provider_id"]: item for item in statuses}
    assert by_id["local_qwen"]["ready"] is True
    assert by_id["local_qwen"]["api_key_source"] == "env"
    assert by_id["deepseek"]["ready"] is True
    assert by_id["deepseek"]["api_key_env"] == "SAFEAGENT_DEEPSEEK_API_KEY"
    assert by_id["codex"]["ready"] is False
    assert by_id["codex"]["reason"] == "provider disabled in config"
    assert "sk-test-not-real" not in str(statuses)
