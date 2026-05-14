from __future__ import annotations

import ast
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOTS = {
    "api",
    "config",
    "core",
    "graphs",
    "helper",
    "models",
    "nodes",
    "services",
    "states",
    "task",
    "util",
}


def test_backend_modules_use_backend_absolute_imports() -> None:
    violations: list[str] = []
    for path in BACKEND_ROOT.rglob("*.py"):
        if any(part in {".venv", ".venv-linux", "__pycache__"} for part in path.parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                if node.level > 0:
                    continue
                module = node.module
            elif isinstance(node, ast.Import):
                module = node.names[0].name
            if not module:
                continue
            root = module.split(".", 1)[0]
            top_level_package = path.relative_to(BACKEND_ROOT).parts[0]
            if root in PACKAGE_ROOTS and root != top_level_package:
                rel_path = path.relative_to(BACKEND_ROOT.parent)
                violations.append(f"{rel_path}:{node.lineno}: {module}")

    assert violations == []
