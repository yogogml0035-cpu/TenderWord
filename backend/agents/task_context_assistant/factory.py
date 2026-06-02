from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend
from deepagents.middleware.filesystem import FilesystemPermission

TASK_CONTEXT_ASSISTANT_NAME = "task_context_assistant"
TASK_CONTEXT_ASSISTANT_ALLOWED_SKILLS = ("rewrite", "edit")
TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE = "/skills/"
TASK_CONTEXT_ASSISTANT_SCRATCH_ROUTE = "/scratch/"
TASK_CONTEXT_ASSISTANT_WORKSPACE_ROUTE = "/workspace/"

TASK_CONTEXT_ASSISTANT_SYSTEM_PROMPT = """
你是 TenderWord 的任务上下文助手。

职责边界：
1. 只在 rewrite / edit 的受控技能、工具和上下文内工作。
2. 需要创建任务时只能调用已注册 tool，不能直接操作 Word COM、不能绕开任务队列。
3. 缺少前置条件时先追问最小必要信息，不要猜测，也不要访问受控路径之外的文件。
4. 只向用户输出结构化摘要、追问或任务创建结果，不暴露隐藏推理或敏感路径。
""".strip()

_FACTORY_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _FACTORY_DIR.parents[1]
_REPO_DIR = _BACKEND_DIR.parent
_SKILLS_SOURCE_DIR = _BACKEND_DIR / "skills"


@dataclass
class TaskContextAssistantFactoryResult:
    agent: Any
    backend: CompositeBackend
    permissions: list[FilesystemPermission]
    skill_sources: list[str]
    runtime_root: Path
    default_root: Path
    scratch_root: Path
    workspace_root: Path
    skills_root: Path
    _tempdir: Any = field(default=None, repr=False)

    def cleanup(self) -> None:
        if self._tempdir is None:
            return
        self._tempdir.cleanup()
        self._tempdir = None


def create_task_context_assistant(
    *,
    model: Any,
    tools: Sequence[Any] | None = None,
    instructions: str = TASK_CONTEXT_ASSISTANT_SYSTEM_PROMPT,
    runtime_root: str | Path | None = None,
    name: str = TASK_CONTEXT_ASSISTANT_NAME,
) -> TaskContextAssistantFactoryResult:
    layout = create_task_context_assistant_backend(runtime_root=runtime_root)
    agent = create_deep_agent(
        model=model,
        tools=list(tools or []),
        system_prompt=instructions,
        skills=list(layout.skill_sources),
        backend=layout.backend,
        permissions=list(layout.permissions),
        name=name,
    )
    layout.agent = agent
    return layout


def create_task_context_assistant_backend(
    *,
    runtime_root: str | Path | None = None,
) -> TaskContextAssistantFactoryResult:
    resolved_runtime_root, tempdir = _resolve_runtime_root(runtime_root)
    default_root = resolved_runtime_root / "default"
    scratch_root = resolved_runtime_root / "scratch"
    workspace_root = resolved_runtime_root / "workspace"
    skills_root = resolved_runtime_root / "skills"

    for directory in (default_root, scratch_root, workspace_root, skills_root):
        directory.mkdir(parents=True, exist_ok=True)

    _copy_allowed_skill_directories(skills_root)

    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=default_root, virtual_mode=True),
        routes={
            TASK_CONTEXT_ASSISTANT_SCRATCH_ROUTE: FilesystemBackend(
                root_dir=scratch_root,
                virtual_mode=True,
            ),
            TASK_CONTEXT_ASSISTANT_WORKSPACE_ROUTE: FilesystemBackend(
                root_dir=workspace_root,
                virtual_mode=True,
            ),
            TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE: FilesystemBackend(
                root_dir=skills_root,
                virtual_mode=True,
            ),
        },
    )

    return TaskContextAssistantFactoryResult(
        agent=None,
        backend=backend,
        permissions=_build_permissions(),
        skill_sources=[TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE],
        runtime_root=resolved_runtime_root,
        default_root=default_root,
        scratch_root=scratch_root,
        workspace_root=workspace_root,
        skills_root=skills_root,
        _tempdir=tempdir,
    )


def _resolve_runtime_root(
    runtime_root: str | Path | None,
) -> tuple[Path, Any]:
    if runtime_root is not None:
        return Path(runtime_root).resolve(), None

    tempdir = tempfile.TemporaryDirectory(
        prefix="task-context-assistant-",
        dir=str(_REPO_DIR / "backend"),
    )
    return Path(tempdir.name).resolve(), tempdir


def _copy_allowed_skill_directories(destination_root: Path) -> None:
    for skill_name in TASK_CONTEXT_ASSISTANT_ALLOWED_SKILLS:
        source_dir = _SKILLS_SOURCE_DIR / skill_name
        target_dir = destination_root / skill_name
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(
            source_dir,
            target_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )


def _build_permissions() -> list[FilesystemPermission]:
    return [
        FilesystemPermission(operations=["read"], paths=["/"], mode="allow"),
        FilesystemPermission(
            operations=["read"],
            paths=[
                "/skills",
                "/skills/",
                "/skills/**",
                "/scratch",
                "/scratch/",
                "/scratch/**",
                "/workspace",
                "/workspace/",
                "/workspace/**",
            ],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["write"],
            paths=[
                "/scratch",
                "/scratch/",
                "/scratch/**",
                "/workspace",
                "/workspace/",
                "/workspace/**",
            ],
            mode="allow",
        ),
        FilesystemPermission(
            operations=["read", "write"],
            paths=["/**"],
            mode="deny",
        ),
    ]


__all__ = [
    "TASK_CONTEXT_ASSISTANT_NAME",
    "TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE",
    "TASK_CONTEXT_ASSISTANT_SCRATCH_ROUTE",
    "TASK_CONTEXT_ASSISTANT_SYSTEM_PROMPT",
    "TASK_CONTEXT_ASSISTANT_WORKSPACE_ROUTE",
    "TaskContextAssistantFactoryResult",
    "create_task_context_assistant",
    "create_task_context_assistant_backend",
]
