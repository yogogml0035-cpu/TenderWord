from __future__ import annotations

from deepagents.backends import CompositeBackend, FilesystemBackend

from backend.agents.task_context_assistant.factory import (
    TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE,
    TASK_CONTEXT_ASSISTANT_SYSTEM_PROMPT,
    TASK_CONTEXT_ASSISTANT_WORKSPACE_ROUTE,
    create_task_context_assistant,
    create_task_context_assistant_backend,
)


def test_factory_builds_deep_agent_with_isolated_backend(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    agent_marker = object()
    tool_marker = object()

    def _fake_create_deep_agent(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return agent_marker

    monkeypatch.setattr(
        "backend.agents.task_context_assistant.factory.create_deep_agent",
        _fake_create_deep_agent,
    )

    result = create_task_context_assistant(
        model="deepseek",
        tools=[tool_marker],
        runtime_root=tmp_path / "runtime",
    )

    kwargs = captured["kwargs"]
    assert result.agent is agent_marker
    assert kwargs["model"] == "deepseek"
    assert kwargs["tools"] == [tool_marker]
    assert kwargs["skills"] == [TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE]
    assert kwargs["backend"] is result.backend
    assert kwargs["permissions"] == result.permissions
    assert kwargs["system_prompt"] == TASK_CONTEXT_ASSISTANT_SYSTEM_PROMPT
    assert kwargs["name"] == "task_context_assistant"


def test_backend_exposes_only_rewrite_skill_root(tmp_path) -> None:
    result = create_task_context_assistant_backend(runtime_root=tmp_path / "runtime")

    assert isinstance(result.backend, CompositeBackend)
    assert isinstance(result.backend.default, FilesystemBackend)
    assert result.backend.default.virtual_mode is True
    assert result.backend.routes[TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE].virtual_mode is True
    assert result.backend.routes[TASK_CONTEXT_ASSISTANT_WORKSPACE_ROUTE].virtual_mode is True

    skill_entries = result.backend.ls(TASK_CONTEXT_ASSISTANT_SKILL_LIBRARY_ROUTE)
    assert skill_entries.error is None
    assert [item["path"] for item in skill_entries.entries or []] == [
        "/skills/rewrite/",
    ]

    rewrite_skill = result.backend.read("/skills/rewrite/SKILL.md")
    assert rewrite_skill.error is None
    assert "name: rewrite" in str(rewrite_skill.file_data["content"])

    hidden_loader = result.backend.read("/skills/loader.py")
    assert hidden_loader.file_data is None
    assert hidden_loader.error == "File '/loader.py' not found"


def test_backend_blocks_repo_root_logs_and_private_absolute_paths(tmp_path) -> None:
    result = create_task_context_assistant_backend(runtime_root=tmp_path / "runtime")

    scratch_write = result.backend.write("/scratch/note.md", "scratch-ok")
    assert scratch_write.error is None

    workspace_write = result.backend.write("/workspace/context.md", "workspace-ok")
    assert workspace_write.error is None

    blocked_paths = [
        "/.env",
        "/ARCHITECTURE.md",
        "/backend/logs/agent-run-1.jsonl",
        "/mnt/d/CompanyProject/TenderWord/AGENTS.md",
    ]
    for path in blocked_paths:
        read_result = result.backend.read(path)
        assert read_result.file_data is None
        assert read_result.error is not None
        assert "not found" in read_result.error.lower()
