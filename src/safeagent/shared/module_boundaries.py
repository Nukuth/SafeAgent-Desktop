from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BoundaryViolation:
    path: str
    line: int
    module: str
    forbidden_import: str
    rule: str

    def to_message(self) -> str:
        return (
            f"{self.path}:{self.line}: {self.rule}: "
            f"{self.module} must not import {self.forbidden_import}"
        )


BOUNDARY_RULES = {
    "safeagent.shared": ("safeagent.server", "safeagent.local_worker"),
    "safeagent.server": ("safeagent.local_worker",),
    "safeagent.local_worker": ("safeagent.server",),
}


def check_module_boundaries(root: Path) -> list[BoundaryViolation]:
    src_root = root / "src"
    violations: list[BoundaryViolation] = []
    for path in sorted((src_root / "safeagent").rglob("*.py")):
        module = _module_name(src_root, path)
        forbidden = _forbidden_for_module(module)
        if not forbidden:
            continue
        for imported, line in _imports(path):
            for forbidden_prefix in forbidden:
                if imported == forbidden_prefix or imported.startswith(forbidden_prefix + "."):
                    violations.append(
                        BoundaryViolation(
                            path=str(path.relative_to(root)),
                            line=line,
                            module=module,
                            forbidden_import=imported,
                            rule="module-boundary",
                        )
                    )
    return violations


def format_boundary_report(violations: list[BoundaryViolation]) -> str:
    if not violations:
        return "OK module boundaries"
    lines = ["FAIL module boundaries"]
    lines.extend(violation.to_message() for violation in violations)
    return "\n".join(lines)


def _module_name(src_root: Path, path: Path) -> str:
    relative = path.relative_to(src_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _forbidden_for_module(module: str) -> tuple[str, ...]:
    for prefix, forbidden in BOUNDARY_RULES.items():
        if module == prefix or module.startswith(prefix + "."):
            return forbidden
    return ()


def _imports(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0 or not node.module:
                continue
            imports.append((node.module, node.lineno))
    return imports
