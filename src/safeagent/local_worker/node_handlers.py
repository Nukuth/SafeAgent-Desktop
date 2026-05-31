from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from safeagent.local_worker.graph_plan import GraphNode
from safeagent.local_worker.graph_runner import GraphState, NodeHandler
from safeagent.local_worker.providers import ModelRequest, ModelResponse, ProviderRegistry
from safeagent.shared.errors import SafeAgentError
from safeagent.shared.redaction import redact_payload


class ModelInvoker(Protocol):
    def invoke(self, *, model: str, purpose: str, prompt: str) -> dict[str, object]:
        ...


@dataclass(slots=True)
class ProviderModelInvoker:
    provider_registry: ProviderRegistry

    def invoke(self, *, model: str, purpose: str, prompt: str) -> dict[str, object]:
        if model == "none":
            return {"model_status": "skipped", "model": "none", "purpose": purpose}
        provider = self.provider_registry.get(model)
        request = ModelRequest(model=model, purpose=purpose, prompt=prompt)
        try:
            response = provider.generate(request)
        except SafeAgentError as exc:
            return {
                "model_status": "unavailable",
                "model": model,
                "purpose": purpose,
                "error": redact_payload(exc.envelope.to_dict()),
            }
        except Exception as exc:
            return {
                "model_status": "error",
                "model": model,
                "purpose": purpose,
                "error": {
                    "code": "model.invocation_failed",
                    "message": "Model invocation failed with unexpected error",
                    "details": redact_payload({"error": str(exc)}),
                },
            }
        return _response_to_public_dict(response, purpose)


def _response_to_public_dict(response: ModelResponse, purpose: str) -> dict[str, object]:
    return {
        "model_status": "completed",
        "model": response.model,
        "purpose": purpose,
        "content": redact_payload(response.content),
        "usage": {
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "cost_estimate": response.cost_estimate,
        },
    }


def _model_for_node(node: GraphNode, state: GraphState) -> str:
    route = state.payload.get("model_route")
    if not isinstance(route, dict):
        return "none"
    if node.model_policy == "none":
        return "none"
    if node.model_policy == "codex_review":
        return str(route.get("review_model") or route.get("primary_model") or "codex")
    return str(route.get("primary_model") or "none")


def _prompt_for_node(node: GraphNode, state: GraphState, purpose: str) -> str:
    content = str(state.payload.get("content", ""))
    profile = str(state.payload.get("profile", ""))
    risk = state.payload.get("policy")
    return (
        f"Task: {content}\n"
        f"Profile: {profile}\n"
        f"Node: {node.node_id}\n"
        f"Role: {node.role}\n"
        f"Purpose: {purpose}\n"
        f"Policy: {risk}\n"
        "Return a concise, auditable result. Do not execute commands or claim approval."
    )


def _maybe_invoke_model(node: GraphNode, state: GraphState, invoker: ModelInvoker | None, purpose: str) -> dict[str, object]:
    model = _model_for_node(node, state)
    if not invoker or model == "none":
        return {"model_status": "skipped", "model": model, "purpose": purpose}
    return invoker.invoke(model=model, purpose=purpose, prompt=_prompt_for_node(node, state, purpose))


def planner_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "objective": state.payload.get("content", ""),
        "selected_profile": state.payload.get("profile", ""),
        "note": "planner placeholder created a structured objective",
        "model": _maybe_invoke_model(node, state, invoker, "planning"),
    }


def shell_agent_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "proposal_type": "command",
        "mode": "readonly_dry_run",
        "note": "shell agent placeholder delegates command validation to executor boundary",
        "model": _maybe_invoke_model(node, state, invoker, "command_proposal"),
    }


def file_agent_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "proposal_type": "file_plan",
        "mode": "plan_only",
        "note": "file agent placeholder does not mutate files",
        "model": _maybe_invoke_model(node, state, invoker, "file_plan"),
    }


def code_agent_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "proposal_type": "patch_plan",
        "mode": "plan_only",
        "note": "code agent placeholder does not edit files",
        "model": _maybe_invoke_model(node, state, invoker, "code_plan"),
    }


def search_agent_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "proposal_type": "search_plan",
        "mode": "search_not_executed",
        "note": "search agent placeholder does not access network",
        "model": _maybe_invoke_model(node, state, invoker, "search_plan"),
    }


def reviewer_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "review_status": "placeholder",
        "note": f"{node.node_id} records review boundary only",
        "model": _maybe_invoke_model(node, state, invoker, "review"),
    }


def human_approval_handler(node: GraphNode, state: GraphState) -> dict[str, object]:
    return {
        "approval_status": "not_requested_by_runner",
        "note": "approval is handled by orchestrator policy gates, not by graph runner",
    }


def executor_handler(node: GraphNode, state: GraphState) -> dict[str, object]:
    return {
        "execution_status": "not_executed",
        "note": "executor placeholder does not run commands inside graph runner",
    }


def summarizer_handler(node: GraphNode, state: GraphState, invoker: ModelInvoker | None = None) -> dict[str, object]:
    return {
        "summary": "placeholder graph summary",
        "task_id": state.task_id,
        "model": _maybe_invoke_model(node, state, invoker, "summary"),
    }


def _bind(handler, invoker: ModelInvoker | None) -> NodeHandler:
    def bound(node: GraphNode, state: GraphState) -> dict[str, object]:
        return handler(node, state, invoker)

    return bound


def build_default_handlers(provider_registry: ProviderRegistry | None = None) -> dict[str, NodeHandler]:
    invoker = ProviderModelInvoker(provider_registry) if provider_registry else None
    return {
        "planner": _bind(planner_handler, invoker),
        "shell_agent": _bind(shell_agent_handler, invoker),
        "file_agent": _bind(file_agent_handler, invoker),
        "code_agent": _bind(code_agent_handler, invoker),
        "test_agent": _bind(reviewer_handler, invoker),
        "search_agent": _bind(search_agent_handler, invoker),
        "rule_reviewer": _bind(reviewer_handler, invoker),
        "codex_reviewer": _bind(reviewer_handler, invoker),
        "human_approval": human_approval_handler,
        "executor": executor_handler,
        "summarizer": _bind(summarizer_handler, invoker),
    }
