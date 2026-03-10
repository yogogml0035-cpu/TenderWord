from __future__ import annotations

import asyncio

from backend.services.user_routing_service import UserRoutingService


class DummyConversationService:
    def __init__(self, latest_rewrite_state=None):
        self._latest_rewrite_state = latest_rewrite_state

    def get_latest_rewrite_state(self, conversation_id: str):
        return self._latest_rewrite_state


def test_route_message_blocks_doc_context_query():
    service = UserRoutingService(conversation_service=DummyConversationService())

    decision = asyncio.run(
        service.route_message(
            conversation_id="conv-1",
            prompt="请总结一下当前文档的第三章",
            model_provider="deepseek",
        )
    )

    assert decision.route == "blocked_doc_context"
    assert decision.error_code == "CHAT_DOC_CONTEXT_REQUIRED"


def test_route_message_returns_no_document_for_explicit_rewrite_without_history():
    service = UserRoutingService(conversation_service=DummyConversationService())

    decision = asyncio.run(
        service.route_message(
            conversation_id="conv-1",
            prompt="请帮我润色这一段内容",
            model_provider="deepseek",
        )
    )

    assert decision.route == "rewrite"
    assert decision.error_code == "REWRITE_NO_DOCUMENT"


def test_route_message_treats_structured_edit_instruction_as_rewrite():
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )

    decision = asyncio.run(
        service.route_message(
            conversation_id="conv-1",
            prompt="4.2、视野角度：≥120°；这个指标前删除星号指标",
            model_provider="deepseek",
        )
    )

    assert decision.route == "rewrite"
    assert decision.error_code is None


def test_route_message_uses_llm_fallback_for_potential_rewrite(monkeypatch):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )

    async def _related(**_kwargs):
        return True

    monkeypatch.setattr(service, "is_rewrite_prompt_related", _related)

    decision = asyncio.run(
        service.route_message(
            conversation_id="conv-1",
            prompt="把这段写得更正式一些",
            model_provider="deepseek",
        )
    )

    assert decision.route == "rewrite"
    assert decision.error_code is None
    assert decision.used_llm is True


def test_route_message_force_rewrite_returns_invalid_when_classifier_rejects(monkeypatch):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )

    async def _unrelated(**_kwargs):
        return False

    monkeypatch.setattr(service, "is_rewrite_prompt_related", _unrelated)

    decision = asyncio.run(
        service.route_message(
            conversation_id="conv-1",
            prompt="今天天气怎么样",
            model_provider="deepseek",
            force_rewrite=True,
        )
    )

    assert decision.route == "rewrite"
    assert decision.error_code == "REWRITE_PROMPT_INVALID"
