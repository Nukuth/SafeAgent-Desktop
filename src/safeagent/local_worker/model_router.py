from __future__ import annotations

from dataclasses import dataclass

from safeagent.shared.enums import RiskLevel


@dataclass(frozen=True, slots=True)
class ModelRoute:
    primary_model: str
    review_model: str | None
    fallback_model: str | None
    max_retry: int
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_model": self.primary_model,
            "review_model": self.review_model,
            "fallback_model": self.fallback_model,
            "max_retry": self.max_retry,
            "reason": self.reason,
        }


class ModelRouter:
    """Deterministic model routing.

    This class only chooses providers. Provider calls are isolated behind
    adapters so safety policy and orchestration do not depend on vendor SDKs.
    """

    def route(
        self,
        *,
        model_policy: str,
        risk_level: RiskLevel,
        uncertainty: str = "low",
        emergency_local: bool = False,
    ) -> ModelRoute:
        if model_policy == "none":
            return ModelRoute("none", None, None, 0, "agent does not require model inference")
        if emergency_local:
            if risk_level in {RiskLevel.HIGH, RiskLevel.EXTREME}:
                return ModelRoute(
                    "local_qwen",
                    None,
                    None,
                    0,
                    "emergency local mode can discuss high-risk tasks but cannot approve them",
                )
            return ModelRoute(
                "local_qwen",
                None,
                None,
                1,
                "emergency local mode routes non-critical reasoning to local Qwen",
            )
        if model_policy == "codex_review":
            return ModelRoute("codex", None, None, 1, "agent is an explicit Codex reviewer")
        if risk_level in {RiskLevel.HIGH, RiskLevel.EXTREME}:
            return ModelRoute(
                "deepseek",
                "codex",
                "codex",
                1,
                "high-risk task uses cheap generation plus Codex review",
            )
        if uncertainty == "high":
            return ModelRoute(
                "deepseek",
                "codex",
                "codex",
                2,
                "high uncertainty escalates review/fallback to Codex",
            )
        return ModelRoute("deepseek", None, "codex", 2, "default low/medium-risk route")
