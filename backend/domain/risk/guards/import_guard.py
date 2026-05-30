from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


DEFAULT_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("domain", ("runtime", "infrastructure", "application", "api", "engines")),
    ("engines", ("runtime", "application", "api")),
    ("infrastructure", ("runtime", "application", "api", "engines")),
    ("api", ("runtime", "infrastructure", "domain", "engines")),
    ("application", ("infrastructure",)),
)

DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "domain.logging",
    "domain.event.test_protocol",
    "runtime.guards.import_guard",
    "application.queries.infrastructure_queries",
    "application.commands.bus_commands",
)


@dataclass(frozen=True)
class ImportViolation:
    file: Path
    line: int
    importer_layer: str
    imported_module: str
    rule: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "file": str(self.file),
            "line": self.line,
            "importer_layer": self.importer_layer,
            "imported_module": self.imported_module,
            "rule": self.rule,
        }


def _module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(rel.parts)


def _layer_for(path: Path, root: Path) -> str | None:
    rel = path.relative_to(root)
    return rel.parts[0] if rel.parts else None


def _iter_imports(tree: ast.AST) -> Iterable[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.lineno, node.module


def _is_allowlisted(module: str, allowlist: Sequence[str]) -> bool:
    return any(module == allowed or module.startswith(f"{allowed}.") for allowed in allowlist)


def _matches_forbidden(imported_module: str, forbidden_roots: Sequence[str]) -> bool:
    return any(
        imported_module == root or imported_module.startswith(f"{root}.")
        for root in forbidden_roots
    )


def check_import_boundaries(
    root: str | Path,
    *,
    rules: Sequence[tuple[str, Sequence[str]]] = DEFAULT_RULES,
    allowlist: Sequence[str] = DEFAULT_ALLOWLIST,
) -> list[ImportViolation]:
    root_path = Path(root).resolve()
    violations: list[ImportViolation] = []

    for file in root_path.rglob("*.py"):
        if "__pycache__" in file.parts:
            continue

        layer = _layer_for(file, root_path)
        if layer is None:
            continue

        module = _module_name(file, root_path)
        if _is_allowlisted(module, allowlist):
            continue

        try:
            source = file.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            source = file.read_text()

        try:
            tree = ast.parse(source, filename=str(file))
        except SyntaxError:
            continue

        forbidden = tuple(next((items for owner, items in rules if owner == layer), ()))
        if not forbidden:
            continue

        for line, imported_module in _iter_imports(tree):
            if _is_allowlisted(imported_module, allowlist):
                continue
            if _matches_forbidden(imported_module, forbidden):
                violations.append(
                    ImportViolation(
                        file=file,
                        line=line,
                        importer_layer=layer,
                        imported_module=imported_module,
                        rule=f"{layer} must not import {', '.join(forbidden)}",
                    )
                )

    return violations


def assert_import_boundaries(
    root: str | Path,
    *,
    rules: Sequence[tuple[str, Sequence[str]]] = DEFAULT_RULES,
    allowlist: Sequence[str] = DEFAULT_ALLOWLIST,
) -> None:
    violations = check_import_boundaries(root, rules=rules, allowlist=allowlist)
    if not violations:
        return

    details = "\n".join(
        f"{item.file}:{item.line}: {item.importer_layer} -> {item.imported_module}"
        for item in violations
    )
    raise AssertionError(f"Import boundary violations:\n{details}")


__all__ = [
    "DEFAULT_ALLOWLIST",
    "DEFAULT_RULES",
    "ImportViolation",
    "assert_import_boundaries",
    "check_import_boundaries",
]
