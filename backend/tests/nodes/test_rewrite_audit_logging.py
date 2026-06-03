from __future__ import annotations

import json
from types import SimpleNamespace

from backend.nodes.skills_nodes import rewrite_nodes


class _FakeGuide:
    def __call__(self, name: str):
        return SimpleNamespace(name=name, instruction="你是重写助手。")


def test_rewrite_text_writes_prompt_and_request_message_stages(tmp_path, monkeypatch):
    audit_path = tmp_path / "rewrite-audit.json"
    request_messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "assembled user prompt"},
    ]

    async def _fake_stream_llm_completion(**kwargs):
        callbacks = kwargs["callbacks"]
        if callbacks.on_request_messages is not None:
            callbacks.on_request_messages(request_messages)
        if kwargs.get("system_prompt") == rewrite_nodes.REWRITE_VERIFY_SYSTEM_PROMPT:
            return "[]"
        return "最终重写结果"

    monkeypatch.setattr(rewrite_nodes, "get_skill_guide", _FakeGuide())
    monkeypatch.setattr(rewrite_nodes, "stream_llm_completion", _fake_stream_llm_completion)

    result = rewrite_nodes.rewrite_text(
        {
            "tender_type": "gngk_hw_cz",
            "rewrite_user_prompt": "请更新交付日期",
            "rewrite_base_text": "原始正文",
        },
        {
            "configurable": {
                "task_audit_log_path": str(audit_path),
                "model_provider": "deepseek",
            }
        },
    )

    payload = json.loads(audit_path.read_text(encoding="utf-8"))

    assert list(payload.keys()) == ["skill_prompt_render", "rewrite_text"]
    assert payload["skill_prompt_render"] == [
        {"role": "system", "content": "你是重写助手。"},
        {
            "role": "user",
            "content": (
                "【当前文档内容】\n原始正文\n\n"
                "【技术参数参考资料】\n（无）\n\n"
                "【用户修改指令】\n请更新交付日期\n\n"
                "【受保护字段要求】\n无"
            ),
        },
    ]
    assert payload["rewrite_text"] == request_messages
    assert result["polished_text"] == "最终重写结果"
    assert result["generate_polished_done"] is True


def test_rewrite_text_does_not_require_audit_path(monkeypatch):
    async def _fake_stream_llm_completion(**kwargs):
        callbacks = kwargs["callbacks"]
        if callbacks.on_request_messages is not None:
            callbacks.on_request_messages(
                [{"role": "user", "content": "should be ignored without path"}]
            )
        if kwargs.get("system_prompt") == rewrite_nodes.REWRITE_VERIFY_SYSTEM_PROMPT:
            return "[]"
        return "无日志也能完成"

    monkeypatch.setattr(rewrite_nodes, "get_skill_guide", _FakeGuide())
    monkeypatch.setattr(rewrite_nodes, "stream_llm_completion", _fake_stream_llm_completion)

    result = rewrite_nodes.rewrite_text(
        {
            "tender_type": "gngk_hw_cz",
            "rewrite_user_prompt": "请修改文本",
            "rewrite_base_text": "原始正文",
        },
        {"configurable": {"model_provider": "deepseek"}},
    )

    assert result["polished_text"] == "无日志也能完成"
    assert result["generate_polished_done"] is True
