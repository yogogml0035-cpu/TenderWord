from __future__ import annotations

import json
from types import SimpleNamespace

from backend.nodes.skills_nodes import edit_nodes


class _FakeGuide:
    def __call__(self, name: str):
        return SimpleNamespace(name=name, instruction="你是编辑助手。")


def test_edit_text_writes_prompt_and_request_message_stages(tmp_path, monkeypatch):
    audit_path = tmp_path / "edit-audit.json"
    request_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "assembled user prompt"},
    ]

    async def _fake_stream_llm_completion(**kwargs):
        callbacks = kwargs["callbacks"]
        callbacks.on_request_messages(request_messages)
        return "最终修改结果"

    monkeypatch.setattr(edit_nodes, "get_skill_guide", _FakeGuide())
    monkeypatch.setattr(edit_nodes, "stream_llm_completion", _fake_stream_llm_completion)

    result = edit_nodes.edit_text(
        {
            "edit_user_prompt": "请更新交付日期",
            "source_section_text": "原始正文",
        },
        {
            "configurable": {
                "task_audit_log_path": str(audit_path),
                "model_provider": "deepseek",
            }
        },
    )

    payload = json.loads(audit_path.read_text(encoding="utf-8"))

    assert list(payload.keys()) == ["skill_prompt_render", "edit_text_request"]
    assert payload["skill_prompt_render"] == [
        {"role": "system", "content": "你是编辑助手。"},
        {
            "role": "user",
            "content": "【当前锚点区正文】\n原始正文\n\n【用户修改指令】\n请更新交付日期",
        },
    ]
    assert payload["edit_text_request"] == request_messages
    assert result["polished_text"] == "最终修改结果"
    assert result["generate_polished_done"] is True


def test_edit_text_does_not_require_audit_path(monkeypatch):
    async def _fake_stream_llm_completion(**kwargs):
        callbacks = kwargs["callbacks"]
        if callbacks.on_request_messages is not None:
            callbacks.on_request_messages(
                [{"role": "user", "content": "should be ignored without path"}]
            )
        return "无日志也能完成"

    monkeypatch.setattr(edit_nodes, "get_skill_guide", _FakeGuide())
    monkeypatch.setattr(edit_nodes, "stream_llm_completion", _fake_stream_llm_completion)

    result = edit_nodes.edit_text(
        {
            "edit_user_prompt": "请修改文本",
            "source_section_text": "原始正文",
        },
        {"configurable": {"model_provider": "deepseek"}},
    )

    assert result["polished_text"] == "无日志也能完成"
    assert result["generate_polished_done"] is True


def test_edit_text_writes_generate_log_artifacts_without_breaking_edit_log(
    tmp_path, monkeypatch
):
    audit_path = tmp_path / "edit-audit.json"
    generate_log_dir = tmp_path / "generate_log"
    generate_log_dir.mkdir(parents=True, exist_ok=True)

    request_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "assembled user prompt"},
    ]

    async def _fake_stream_llm_completion(**kwargs):
        callbacks = kwargs["callbacks"]
        callbacks.on_request_messages(request_messages)
        return "最终修改结果"

    monkeypatch.setattr(edit_nodes, "get_skill_guide", _FakeGuide())
    monkeypatch.setattr(edit_nodes, "stream_llm_completion", _fake_stream_llm_completion)
    monkeypatch.setattr(
        "backend.util.log_util.prompt_log.get_generate_prompt_log_dir",
        lambda anchor_file: generate_log_dir,
    )

    result = edit_nodes.edit_text(
        {
            "edit_user_prompt": "请更新交付日期",
            "source_section_text": "原始正文",
        },
        {
            "configurable": {
                "task_id": "task-edit-42",
                "task_audit_log_path": str(audit_path),
                "model_provider": "deepseek",
            }
        },
    )

    created_files = sorted(generate_log_dir.glob("prompt_edit_task-edit-42_*"))
    assert len(created_files) == 2

    prompt_file = next(p for p in created_files if p.name.endswith("_edit_prompt.txt"))
    generated_file = next(
        p for p in created_files if p.name.endswith("_edit_generated_content.txt")
    )
    prompt_text = prompt_file.read_text(encoding="utf-8")

    assert "你是编辑助手。" in prompt_text
    assert "【用户修改指令】\n请更新交付日期" in prompt_text
    assert generated_file.read_text(encoding="utf-8") == "最终修改结果"

    payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert list(payload.keys()) == ["skill_prompt_render", "edit_text_request"]
    assert payload["edit_text_request"] == request_messages

    assert result["polished_text"] == "最终修改结果"
    assert result["generate_polished_done"] is True
