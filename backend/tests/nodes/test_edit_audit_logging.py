from __future__ import annotations

import json
from types import SimpleNamespace

from backend.nodes.skills_nodes import edit_nodes


class _FakeRegistry:
    def get_definition(self, name: str):
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

    monkeypatch.setattr(edit_nodes, "get_skill_registry", lambda: _FakeRegistry())
    monkeypatch.setattr(edit_nodes, "stream_llm_completion", _fake_stream_llm_completion)

    result = edit_nodes.edit_text(
        {
            "edit_user_prompt": "请更新交付日期",
            "origin_tender_params": "原始正文",
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

    monkeypatch.setattr(edit_nodes, "get_skill_registry", lambda: _FakeRegistry())
    monkeypatch.setattr(edit_nodes, "stream_llm_completion", _fake_stream_llm_completion)

    result = edit_nodes.edit_text(
        {
            "edit_user_prompt": "请修改文本",
            "origin_tender_params": "原始正文",
        },
        {"configurable": {"model_provider": "deepseek"}},
    )

    assert result["polished_text"] == "无日志也能完成"
    assert result["generate_polished_done"] is True
