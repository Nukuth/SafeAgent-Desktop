from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from safeagent.local_worker.config_sync import load_json_config
from safeagent.shared.errors import SafeAgentError, TransientUpstreamError, ValidationError
from safeagent.shared.enums import Severity


@dataclass(frozen=True, slots=True)
class ModelRequest:
    model: str
    prompt: str
    purpose: str


@dataclass(frozen=True, slots=True)
class ModelResponse:
    model: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate: float = 0.0


class ModelProvider(Protocol):
    def generate(self, request: ModelRequest) -> ModelResponse:
        ...


class ProviderNotConfiguredError(SafeAgentError):
    def __init__(self, model: str) -> None:
        super().__init__(
            "provider.not_configured",
            "local_worker.providers",
            f"Model provider is not configured for {model}",
            severity=Severity.WARNING,
            retriable=False,
            details={"model": model},
        )


class NullProvider:
    """Explicit no-op provider used until DeepSeek/Codex adapters are configured."""

    def generate(self, request: ModelRequest) -> ModelResponse:
        raise ProviderNotConfiguredError(request.model)


@dataclass(frozen=True, slots=True)
class OpenAICompatibleProviderConfig:
    provider_id: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 60.0
    system_prompt: str = "You are a careful assistant. Do not approve high-risk actions."

    def is_configured(self) -> bool:
        return bool(self.base_url.strip() and self.model.strip())

    def public_status(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "base_url": self.base_url,
            "model": self.model,
            "has_api_key": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
        }


class OpenAICompatibleProvider:
    """Minimal standard-library provider for OpenAI-compatible chat APIs."""

    def __init__(self, config: OpenAICompatibleProviderConfig) -> None:
        self.config = config

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.config.is_configured():
            raise ProviderNotConfiguredError(request.model)
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.config.system_prompt,
                },
                {"role": "user", "content": request.prompt},
            ],
            "temperature": 0.2,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        try:
            http_request = Request(url, data=body, headers=headers, method="POST")
            with urlopen(http_request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise TransientUpstreamError(
                "local_worker.providers",
                f"Model provider HTTP error: {exc.code}",
                {"provider_id": self.config.provider_id, "model": request.model, "status_code": exc.code},
            ) from exc
        except URLError as exc:
            raise TransientUpstreamError(
                "local_worker.providers",
                "Model provider endpoint is unreachable",
                {"provider_id": self.config.provider_id, "model": request.model, "reason": str(exc.reason)},
            ) from exc
        except TimeoutError as exc:
            raise TransientUpstreamError(
                "local_worker.providers",
                "Model provider request timed out",
                {"provider_id": self.config.provider_id, "model": request.model},
            ) from exc

        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ValidationError(
                "local_worker.providers",
                "Model provider response does not match OpenAI-compatible chat format",
                {"provider_id": self.config.provider_id, "model": request.model},
            ) from exc

        usage = data.get("usage", {}) if isinstance(data, dict) else {}
        return ModelResponse(
            model=self.config.model,
            content=str(content),
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            cost_estimate=0.0,
        )


class OpenAICompatibleLocalProvider(OpenAICompatibleProvider):
    """Compatibility alias for local OpenAI-compatible chat APIs."""


@dataclass(frozen=True, slots=True)
class ModelProviderSpec:
    provider_id: str
    provider_type: str
    enabled: bool
    base_url: str
    model: str
    api_key_env: str
    default_api_key: str = ""
    timeout_seconds: float = 60.0
    system_prompt: str = "You are a careful assistant. Do not approve high-risk actions."

    def api_key_from_env(self, env: Mapping[str, str]) -> str:
        return env.get(self.api_key_env, self.default_api_key)


class ProviderRegistry:
    def __init__(self, providers: dict[str, ModelProvider] | None = None) -> None:
        self.providers = providers or {}

    def get(self, model: str) -> ModelProvider:
        provider = self.providers.get(model)
        if provider is None:
            return NullProvider()
        return provider

    def public_status(self) -> dict[str, object]:
        status: dict[str, object] = {}
        for model, provider in self.providers.items():
            config = getattr(provider, "config", None)
            if hasattr(config, "public_status"):
                status[model] = config.public_status()
            else:
                status[model] = {"provider_id": model, "configured": True}
        return status


def model_provider_config_status(
    config_path: Path,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    effective_env = os.environ if env is None else env
    statuses: list[dict[str, object]] = []
    for provider_id, spec in load_model_provider_specs(config_path).items():
        api_key = spec.api_key_from_env(effective_env)
        key_source = "env" if spec.api_key_env in effective_env else "default" if spec.default_api_key else "missing"
        ready = bool(spec.enabled and spec.base_url.strip() and spec.model.strip() and api_key)
        statuses.append(
            {
                "provider_id": provider_id,
                "type": spec.provider_type,
                "enabled": spec.enabled,
                "ready": ready,
                "base_url": spec.base_url,
                "model": spec.model,
                "api_key_env": spec.api_key_env,
                "has_api_key": bool(api_key),
                "api_key_source": key_source,
                "timeout_seconds": spec.timeout_seconds,
                "reason": _provider_status_reason(spec, api_key),
            }
        )
    return statuses


def load_model_provider_specs(config_path: Path) -> dict[str, ModelProviderSpec]:
    data = load_json_config(config_path)
    if not isinstance(data, dict) or not isinstance(data.get("providers"), dict):
        raise ValidationError(
            "local_worker.providers",
            "Model config must contain a providers object",
            {"path": str(config_path)},
        )

    specs: dict[str, ModelProviderSpec] = {}
    for provider_id, raw in data["providers"].items():
        if not isinstance(raw, dict):
            raise ValidationError(
                "local_worker.providers",
                "Model provider config must be an object",
                {"path": str(config_path), "provider_id": str(provider_id)},
            )
        default_api_key = str(raw.get("default_api_key", ""))
        if _looks_like_secret(default_api_key):
            raise ValidationError(
                "local_worker.providers",
                "Model config must not contain real API keys",
                {"path": str(config_path), "provider_id": str(provider_id), "field": "default_api_key"},
            )
        try:
            specs[str(provider_id)] = ModelProviderSpec(
                provider_id=str(provider_id),
                provider_type=str(raw["type"]),
                enabled=bool(raw.get("enabled", True)),
                base_url=str(raw.get("base_url", "")),
                model=str(raw.get("model", "")),
                api_key_env=str(raw["api_key_env"]),
                default_api_key=default_api_key,
                timeout_seconds=float(raw.get("timeout_seconds", "60")),
                system_prompt=str(raw.get("system_prompt", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                "local_worker.providers",
                "Model provider config is invalid",
                {"path": str(config_path), "provider_id": str(provider_id), "error": str(exc)},
            ) from exc

    return specs


def build_provider_registry_from_config(
    config_path: Path,
    env: Mapping[str, str] | None = None,
) -> ProviderRegistry:
    effective_env = os.environ if env is None else env
    providers: dict[str, ModelProvider] = {}
    for provider_id, spec in load_model_provider_specs(config_path).items():
        if not spec.enabled:
            continue
        if spec.provider_type != "openai_compatible":
            raise ValidationError(
                "local_worker.providers",
                "Unsupported model provider type",
                {"provider_id": provider_id, "provider_type": spec.provider_type},
            )
        api_key = spec.api_key_from_env(effective_env)
        if not (spec.base_url.strip() and spec.model.strip() and api_key):
            continue
        provider_config = OpenAICompatibleProviderConfig(
            provider_id=provider_id,
            base_url=spec.base_url,
            api_key=api_key,
            model=spec.model,
            timeout_seconds=spec.timeout_seconds,
            system_prompt=spec.system_prompt,
        )
        provider_cls = OpenAICompatibleLocalProvider if provider_id == "local_qwen" else OpenAICompatibleProvider
        providers[provider_id] = provider_cls(provider_config)
    return ProviderRegistry(providers)


def build_provider_registry(
    *,
    local_qwen_base_url: str,
    local_qwen_model: str,
    local_qwen_api_key: str,
    deepseek_base_url: str,
    deepseek_model: str,
    deepseek_api_key: str,
    codex_base_url: str,
    codex_model: str,
    codex_api_key: str,
    timeout_seconds: float,
) -> ProviderRegistry:
    providers: dict[str, ModelProvider] = {
        "local_qwen": OpenAICompatibleProvider(
            OpenAICompatibleProviderConfig(
                provider_id="local_qwen",
                base_url=local_qwen_base_url,
                api_key=local_qwen_api_key,
                model=local_qwen_model,
                timeout_seconds=timeout_seconds,
                system_prompt="You are a local emergency assistant. Do not approve high-risk actions.",
            )
        )
    }
    if deepseek_base_url and deepseek_model and deepseek_api_key:
        providers["deepseek"] = OpenAICompatibleProvider(
            OpenAICompatibleProviderConfig(
                provider_id="deepseek",
                base_url=deepseek_base_url,
                api_key=deepseek_api_key,
                model=deepseek_model,
                timeout_seconds=timeout_seconds,
                system_prompt="You are a planning and coding assistant. Produce cautious, auditable outputs.",
            )
        )
    if codex_base_url and codex_model and codex_api_key:
        providers["codex"] = OpenAICompatibleProvider(
            OpenAICompatibleProviderConfig(
                provider_id="codex",
                base_url=codex_base_url,
                api_key=codex_api_key,
                model=codex_model,
                timeout_seconds=timeout_seconds,
                system_prompt="You are a critical reviewer. Identify risks and safer alternatives. Do not execute actions.",
            )
        )
    return ProviderRegistry(providers)


def _looks_like_secret(value: str) -> bool:
    lowered = value.lower()
    return value.startswith("sk-") or "bearer " in lowered or "api_key" in lowered or "password" in lowered


def _provider_status_reason(spec: ModelProviderSpec, api_key: str) -> str:
    if not spec.enabled:
        return "provider disabled in config"
    missing: list[str] = []
    if not spec.base_url.strip():
        missing.append("base_url")
    if not spec.model.strip():
        missing.append("model")
    if not api_key:
        missing.append(spec.api_key_env)
    if missing:
        return "missing " + ", ".join(missing)
    return "ready"
