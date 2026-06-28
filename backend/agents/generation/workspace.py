from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import BackendProtocol

from backend.agents.log_naming import sanitize_agent_log_part
from backend.agents.generation.types import GenerationAgentProtocolError


MAX_REVISION_ROUNDS = 3
CONTENT_AGENT_WORKSPACE_ROOT = (
    Path(__file__).resolve().parents[2] / "context_log" / "content_agent_workspace"
)

GENERATION_CONTEXT_PATH = "/inputs/generation_context.md"
DRAFT_PATH = "/drafts/round-1.md"
FINAL_POLISHED_TEXT_PATH = "/final/polished_text.md"


def audit_path(round_index: int) -> str:
    return f"/audits/round-{round_index}.json"


def revision_path(round_index: int) -> str:
    return f"/revisions/round-{round_index}.md"


def sanitize_workspace_part(value: str) -> str:
    return sanitize_agent_log_part(value, fallback="content-agent")


def create_workspace_dir(
    task_id: str,
    *,
    project_number: str | None = None,
    project_name: str | None = None,
    now: float | None = None,
) -> Path:
    CONTENT_AGENT_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))
    # 命名只体现项目编号和项目名；task_id 不再作为前缀，仅在 project 信息全空时兜底，
    # 以保证目录可追溯且不与 task_id 前缀耦合。
    parts: list[str] = []
    for value in (project_number, project_name):
        text = str(value or "").strip()
        if not text:
            continue
        parts.append(sanitize_workspace_part(text))
    stem = "_".join(parts) if parts else sanitize_workspace_part(task_id)
    base = CONTENT_AGENT_WORKSPACE_ROOT / f"{stem}_{timestamp}"
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        return base
    path = CONTENT_AGENT_WORKSPACE_ROOT / f"{base.name}_{uuid.uuid4().hex[:6]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_workspace_backend(workspace_dir: Path) -> FilesystemBackend:
    return FilesystemBackend(root_dir=workspace_dir, virtual_mode=True)


def get_configurable(config: dict[str, Any] | None) -> dict[str, Any]:
    return config.get("configurable", {}) if isinstance(config, dict) else {}


def get_workspace_backend(config: dict[str, Any] | None) -> BackendProtocol | None:
    backend = get_configurable(config).get("content_agent_backend")
    return backend if isinstance(backend, BackendProtocol) else None


def read_backend_text(backend: BackendProtocol, path: str) -> str:
    result = backend.read(path)
    if result.error or result.file_data is None:
        raise GenerationAgentProtocolError(f"无法读取智能体工作区文件 {path}: {result.error}")
    return str(result.file_data.get("content") or "")


def read_backend_text_optional(backend: BackendProtocol, path: str) -> str | None:
    result = backend.read(path)
    if result.error or result.file_data is None:
        return None
    return str(result.file_data.get("content") or "")


def write_backend_text(backend: BackendProtocol, path: str, content: str) -> None:
    result = backend.write(path, str(content or ""))
    if result.error:
        raise GenerationAgentProtocolError(f"无法写入智能体工作区文件 {path}: {result.error}")


def overwrite_backend_text(backend: BackendProtocol, path: str, content: str) -> None:
    next_content = str(content or "")
    existing = read_backend_text_optional(backend, path)
    if existing is None:
        write_backend_text(backend, path, next_content)
        return
    if existing == next_content:
        return
    result = backend.edit(path, existing, next_content)
    if result.error:
        raise GenerationAgentProtocolError(f"无法覆盖智能体工作区文件 {path}: {result.error}")


def render_generation_context_markdown(payload: dict[str, Any]) -> str:
    return (
        "# Generation Context\n\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}\n"
        "```\n"
    )


def write_generation_context(backend: BackendProtocol, payload: dict[str, Any]) -> None:
    write_backend_text(backend, GENERATION_CONTEXT_PATH, render_generation_context_markdown(payload))


def parse_generation_context_markdown(content: str) -> dict[str, Any]:
    text = str(content or "").strip()
    match = re.search(r"```json\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    raw_json = match.group(1) if match else text
    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise GenerationAgentProtocolError("generation_context.md 必须包含合法 JSON code block") from exc
    if not isinstance(parsed, dict):
        raise GenerationAgentProtocolError("generation_context.md 的 JSON 必须是对象")
    return parsed


def read_generation_context(backend: BackendProtocol) -> dict[str, Any]:
    return parse_generation_context_markdown(read_backend_text(backend, GENERATION_CONTEXT_PATH))


def get_generation_context(config: dict[str, Any] | None) -> dict[str, Any]:
    context = get_configurable(config).get("generation_agent_context")
    return context if isinstance(context, dict) else {}


def context_value(
    state: dict[str, Any],
    config: dict[str, Any] | None,
    key: str,
    default: Any = "",
) -> Any:
    context = get_generation_context(config)
    value = context.get(key)
    if value is not None:
        return value
    return state.get(key, default)


def ensure_round_within_protocol(
    round_index: int,
    *,
    artifact_type: str = "round",
) -> int:
    """校验轮次下标必须在协议允许的 [1, MAX_REVISION_ROUNDS] 范围内。

    主流程最多只允许 3 轮审核/修订；第 3 轮后必须停止返修，交付最终正文。
    任何写入或推断得到的第 4 轮（及以上）都必须在此处拦截，
    抛出“协议轮次已用尽”的受控错误，而不是把越界轮次传给写文件逻辑。
    """
    normalized = int(round_index)
    if normalized < 1 or normalized > MAX_REVISION_ROUNDS:
        raise GenerationAgentProtocolError(
            f"协议轮次已用尽：{artifact_type} 第 {normalized} 轮超出允许范围 "
            f"[1, {MAX_REVISION_ROUNDS}]，不得再写第 {normalized} 轮产物"
        )
    return normalized


def infer_next_audit_round(backend: BackendProtocol) -> int:
    for round_index in range(1, MAX_REVISION_ROUNDS + 1):
        result = backend.read(audit_path(round_index))
        if result.error or result.file_data is None:
            return round_index
    # 第 3 轮审核产物已存在：协议轮次用尽，不得再写第 4 轮审核。
    raise GenerationAgentProtocolError(
        f"协议轮次已用尽：已存在 {MAX_REVISION_ROUNDS} 轮审核产物，"
        f"不得再写第 {MAX_REVISION_ROUNDS + 1} 轮审核"
    )


def infer_current_text_path(backend: BackendProtocol) -> str:
    for round_index in range(MAX_REVISION_ROUNDS, 0, -1):
        result = backend.read(revision_path(round_index))
        if not result.error and result.file_data is not None:
            return revision_path(round_index)
    return DRAFT_PATH


def infer_next_revision_round(backend: BackendProtocol) -> int:
    for round_index in range(1, MAX_REVISION_ROUNDS + 1):
        result = backend.read(revision_path(round_index))
        if result.error or result.file_data is None:
            return round_index
    # 第 3 轮修订产物已存在：协议轮次用尽，不得再写第 4 轮修订。
    raise GenerationAgentProtocolError(
        f"协议轮次已用尽：已存在 {MAX_REVISION_ROUNDS} 轮修订产物，"
        f"不得再写第 {MAX_REVISION_ROUNDS + 1} 轮修订"
    )


def validate_round_protocol(workspace_dir: Path) -> None:
    """校验工作区轮次产物路径合法。

    历史或异常 runner 可能留下越界产物（如 round-4）。这类产物不参与交付，
    也不作为 fatal：合法轮次范围外的 round-N 文件忽略，只对非法文件名报错。
    越界文件会被调用方在读取/统计阶段排除，确保 last_audit_round /
    revision_rounds 不会包含第 4 轮及以后。
    """
    for folder_name in ("audits", "revisions"):
        folder = workspace_dir / folder_name
        if not folder.exists():
            continue
        for path in folder.iterdir():
            match = re.fullmatch(r"round-(\d+)\.(?:json|md)", path.name)
            if not match:
                raise GenerationAgentProtocolError(f"智能体工作区存在非法路径: /{folder_name}/{path.name}")
            round_index = int(match.group(1))
            if round_index < 1:
                raise GenerationAgentProtocolError(f"智能体工作区存在非法轮次文件: /{folder_name}/{path.name}")
            # round_index > MAX_REVISION_ROUNDS 视为历史越界产物，忽略而非 fatal。


__all__ = [
    "CONTENT_AGENT_WORKSPACE_ROOT",
    "DRAFT_PATH",
    "FINAL_POLISHED_TEXT_PATH",
    "GENERATION_CONTEXT_PATH",
    "MAX_REVISION_ROUNDS",
    "audit_path",
    "context_value",
    "create_workspace_backend",
    "create_workspace_dir",
    "ensure_round_within_protocol",
    "get_configurable",
    "get_generation_context",
    "get_workspace_backend",
    "infer_current_text_path",
    "infer_next_audit_round",
    "infer_next_revision_round",
    "parse_generation_context_markdown",
    "read_backend_text",
    "read_backend_text_optional",
    "read_generation_context",
    "render_generation_context_markdown",
    "revision_path",
    "overwrite_backend_text",
    "validate_round_protocol",
    "write_backend_text",
    "write_generation_context",
]
