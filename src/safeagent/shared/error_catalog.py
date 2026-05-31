from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorCodeSpec:
    code: str
    owner: str
    retriable: bool
    description: str
    operator_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "owner": self.owner,
            "retriable": self.retriable,
            "description": self.description,
            "operator_hint": self.operator_hint,
        }


ERROR_CATALOG: dict[str, ErrorCodeSpec] = {
    "auth.failed": ErrorCodeSpec(
        code="auth.failed",
        owner="shared.auth",
        retriable=False,
        description="Authentication or remote permission check failed.",
        operator_hint="Check bearer tokens and remote permission headers before retrying.",
    ),
    "dependency.missing": ErrorCodeSpec(
        code="dependency.missing",
        owner="shared.errors",
        retriable=False,
        description="A required local dependency is not installed or not importable.",
        operator_hint="Run the documented project-local installation command, then rerun doctor.",
    ),
    "model.invocation_failed": ErrorCodeSpec(
        code="model.invocation_failed",
        owner="local_worker.node_handlers",
        retriable=True,
        description="A model provider raised an unexpected exception inside a node.",
        operator_hint="Inspect provider logs locally; do not bypass policy or approval gates to recover.",
    ),
    "policy.denied": ErrorCodeSpec(
        code="policy.denied",
        owner="local_worker.policy",
        retriable=False,
        description="Local safety policy denied a command or operation.",
        operator_hint="Use a safer task, narrower path, or explicit approval flow instead of forcing execution.",
    ),
    "provider.not_configured": ErrorCodeSpec(
        code="provider.not_configured",
        owner="local_worker.providers",
        retriable=False,
        description="A requested model provider has no usable local configuration.",
        operator_hint="Set the provider environment variables locally; never write API keys into cloud storage.",
    ),
    "upstream.transient": ErrorCodeSpec(
        code="upstream.transient",
        owner="local_worker.client",
        retriable=True,
        description="A networked upstream dependency failed transiently.",
        operator_hint="Retry after checking network, server availability, and token configuration.",
    ),
    "validation.failed": ErrorCodeSpec(
        code="validation.failed",
        owner="shared.errors",
        retriable=False,
        description="Input, configuration, graph, or state validation failed.",
        operator_hint="Read details.module and details fields; fix the invalid input before retrying.",
    ),
    "worker.task_failed": ErrorCodeSpec(
        code="worker.task_failed",
        owner="local_worker.worker",
        retriable=False,
        description="One task failed inside the local worker task-isolation boundary.",
        operator_hint="Inspect the local worker audit log for the failed task; do not stop processing unrelated tasks.",
    ),
    "worker.report_failed": ErrorCodeSpec(
        code="worker.report_failed",
        owner="local_worker.worker",
        retriable=True,
        description="The worker caught a task failure but failed to report that failure to the control plane.",
        operator_hint="Check control-plane reachability and auth; the local audit log remains authoritative.",
    ),
}


def is_registered_error_code(code: str) -> bool:
    return code in ERROR_CATALOG


def find_error_codes_in_source(root: Path) -> dict[str, list[str]]:
    discovered: dict[str, list[str]] = {}
    for path in root.rglob("*.py"):
        if _skip_path(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for code, lineno in _iter_error_code_literals(tree):
            discovered.setdefault(code, []).append(f"{path}:{lineno}")
    return discovered


def find_unregistered_error_codes(root: Path) -> dict[str, list[str]]:
    discovered = find_error_codes_in_source(root)
    return {
        code: locations
        for code, locations in sorted(discovered.items())
        if code not in ERROR_CATALOG
    }


def _iter_error_code_literals(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _call_name(node.func)
            if func_name in {"SafeAgentError", "ErrorEnvelope"}:
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    yield node.args[0].value, node.lineno
                for keyword in node.keywords:
                    if (
                        keyword.arg == "code"
                        and isinstance(keyword.value, ast.Constant)
                        and isinstance(keyword.value.value, str)
                    ):
                        yield keyword.value.value, node.lineno
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "code"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and "." in value.value
                ):
                    yield value.value, node.lineno


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _skip_path(path: Path) -> bool:
    parts = set(path.parts)
    return bool(
        {
            ".venv",
            ".runtime",
            "__pycache__",
            "safeagent_workspace.egg-info",
        }
        & parts
    )
