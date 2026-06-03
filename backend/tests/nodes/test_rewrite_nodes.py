from __future__ import annotations

import importlib


node_module = importlib.import_module("backend.nodes.skills_nodes.rewrite_nodes")


def test_build_rewrite_prompt_uses_runtime_contract_and_protected_fields() -> None:
    system_prompt, user_prompt = node_module._build_rewrite_prompt(
        state={
            "polished_text": "一、项目概况\n交付日期：合同签订后 30 日内\n付款方式：验收后付款",
            "tender_params": "技术参数参考",
        },
        rewrite_user_prompt="请把质保期改为 3 年",
        protected_markers=("交付日期：", "付款方式："),
    )

    assert "先复制全文，再局部修改" in system_prompt
    assert "输出长度必须覆盖【当前文档内容】的全部内容" in system_prompt
    assert "create_rewrite_task_tool" not in system_prompt
    assert "任务上下文助手" not in system_prompt
    assert "【当前文档内容】" in user_prompt
    assert "交付日期：合同签订后 30 日内" in user_prompt
    assert "【技术参数参考资料】\n技术参数参考" in user_prompt
    assert "交付日期： -> 付款方式：" in user_prompt


def test_rewrite_text_audits_repairs_protected_fields_and_emits_agent_steps(
    monkeypatch,
) -> None:
    base_text = (
        "一、项目概况\n"
        "交付日期：合同签订后 30 日内\n"
        "付款方式：验收后付款\n"
        "二、售后服务\n"
        "提供 1 年质保"
    )
    draft_text = "一、项目概况\n付款方式：验收后付款\n二、售后服务\n提供 3 年质保"
    revised_text = (
        "一、项目概况\n"
        "交付日期：合同签订后 30 日内\n"
        "付款方式：验收后付款\n"
        "二、售后服务\n"
        "提供 3 年质保"
    )
    calls: list[dict[str, object]] = []
    events: list[object] = []

    async def fake_stream_llm_completion(**kwargs):
        calls.append(kwargs)
        callbacks = kwargs.get("callbacks")
        if callbacks and getattr(callbacks, "on_request_messages", None):
            callbacks.on_request_messages(
                [
                    {"role": "system", "content": kwargs.get("system_prompt", "")},
                    {"role": "user", "content": kwargs.get("user_prompt", "")},
                ]
            )

        system_prompt = str(kwargs.get("system_prompt") or "")
        if system_prompt == node_module.REWRITE_VERIFY_SYSTEM_PROMPT:
            return "[]"
        if system_prompt == node_module.REWRITE_REVISE_SYSTEM_PROMPT:
            user_prompt = str(kwargs.get("user_prompt") or "")
            assert "【当前文档内容】" in user_prompt
            assert "交付日期：合同签订后 30 日内" in user_prompt
            assert "重写后正文缺少受保护字段行 `交付日期：`。" in user_prompt
            return revised_text
        return draft_text

    monkeypatch.setattr(
        node_module,
        "stream_llm_completion",
        fake_stream_llm_completion,
    )

    result = node_module.rewrite_text(
        {
            "tender_type": "xjcg",
            "rewrite_base_text": base_text,
            "rewrite_user_prompt": "请把质保期改为 3 年",
        },
        {
            "configurable": {
                "task_id": "task-rewrite-1",
                "task_kind": "rewrite",
                "model_provider": "deepseek",
                "agent_step_callback": events.append,
                "suppress_llm_stdout": True,
            }
        },
    )

    assert result["polished_text"] == revised_text
    assert result["generate_polished_done"] is True
    assert len(calls) == 4
    assert "先复制全文，再局部修改" in str(calls[0].get("system_prompt") or "")
    assert [str(call.get("system_prompt") or "") for call in calls[1:]] == [
        node_module.REWRITE_VERIFY_SYSTEM_PROMPT,
        node_module.REWRITE_REVISE_SYSTEM_PROMPT,
        node_module.REWRITE_VERIFY_SYSTEM_PROMPT,
    ]

    payloads = [event.model_dump(mode="json") for event in events]
    assert [payload["node"] for payload in payloads] == [
        "rewrite_generate_agent",
        "rewrite_verify_agent",
        "rewrite_revise_agent",
        "rewrite_verify_agent",
        "rewrite_agent",
    ]
    assert all(payload["task_kind"] == "rewrite" for payload in payloads)
    assert payloads[0]["content_agent"]["phase"] == "draft"
    assert payloads[1]["content_agent"]["rounds"][1]["issue_count"] == 1
    assert payloads[1]["findings"][0]["evidence"] == "重写后正文缺少受保护字段行 `交付日期：`。"
    assert payloads[2]["content"] == revised_text
    assert payloads[3]["content_agent"]["phase"] == "audit"
    assert payloads[3]["findings"] == []
    assert payloads[4]["content_agent"]["phase"] == "final"
    assert payloads[4]["content_agent"]["final_result"]["content"] == revised_text
