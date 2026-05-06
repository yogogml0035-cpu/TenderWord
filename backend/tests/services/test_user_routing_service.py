import asyncio

from backend.prompts.routing_prompt import REPLY_ROUTE_LITERAL, REWRITE_ROUTE_LITERAL
from backend.services.conversation_service import ConversationService
from backend.services.user_routing_service import UserRoutingService
from backend.skills.types import SkillExecutorBinding, SkillSummary


class _FakeSkillRegistry:
    def list_skill_summaries(self):
        return (
            SkillSummary(
                name="rewrite",
                description="当用户希望基于当前会话里已经生成过的招标正文继续修改时使用。",
            ),
        )

    def list_skill_ids(self):
        return ("rewrite",)

    def get_executor_binding(self, skill_id: str):
        return SkillExecutorBinding(
            skill_id=skill_id,
            executor_kind="task",
            dispatch_key=skill_id,
            route_literal=REWRITE_ROUTE_LITERAL,
        )


def _seed_rewrite_history(service: ConversationService, conversation_id: str) -> None:
    service.seed_generate_success(
        conversation_id,
        {
            "tender_type": "xjcg",
            "prepared_doc_path": "D:/UploadFiles/generated.docx",
            "polished_text": "第2包：运动平板心脏功能检测系统从2。",
            "project_name": "测试项目",
            "project_number": "ZBGG-2026-001",
        },
        model="deepseek",
    )


def test_rewrite_intent_routes_without_waiting_for_llm(monkeypatch) -> None:
    conversation_service = ConversationService()
    _seed_rewrite_history(conversation_service, "conv-1")
    routing_service = UserRoutingService(
        conversation_service=conversation_service,
        skill_registry=_FakeSkillRegistry(),
    )
    monkeypatch.setattr(
        routing_service,
        "_write_skill_directory_route_audit",
        lambda **_kwargs: "deterministic-rewrite.json",
    )

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("rewrite fast-path should not call route LLM")

    monkeypatch.setattr(
        "backend.services.user_routing_service.stream_llm_completion",
        fail_if_called,
    )

    decision = asyncio.run(
        routing_service.stream_route_or_reply(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "第2包：运动平板心脏功能检测系统从2，技术参数标注"}],
            latest_user_message="第2包：运动平板心脏功能检测系统从2，技术参数标注",
            model_provider="deepseek",
        )
    )

    assert decision.route == REWRITE_ROUTE_LITERAL
    assert decision.skill_id == "rewrite"
    assert decision.used_llm is False
    assert decision.latest_rewrite_state is not None
    assert decision.rewrite_log_path == "deterministic-rewrite.json"


def test_capability_question_stays_on_llm_reply_path(monkeypatch) -> None:
    conversation_service = ConversationService()
    _seed_rewrite_history(conversation_service, "conv-1")
    routing_service = UserRoutingService(
        conversation_service=conversation_service,
        skill_registry=_FakeSkillRegistry(),
    )
    calls = []

    async def fake_stream_llm_completion(*_args, **kwargs):
        calls.append(kwargs)
        return "可以，生成完成后可以继续下达修改指令。"

    monkeypatch.setattr(
        "backend.services.user_routing_service.stream_llm_completion",
        fake_stream_llm_completion,
    )

    decision = asyncio.run(
        routing_service.stream_route_or_reply(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "你可以修改文档吗？"}],
            latest_user_message="你可以修改文档吗？",
            model_provider="deepseek",
        )
    )

    assert decision.route == REPLY_ROUTE_LITERAL
    assert decision.used_llm is True
    assert decision.reply_text == "可以，生成完成后可以继续下达修改指令。"
    assert len(calls) == 1
