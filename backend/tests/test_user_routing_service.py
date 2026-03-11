from __future__ import annotations

import asyncio

from backend.services.user_routing_service import (
    NO_DOCUMENT_HINT_TEXT,
    REWRITE_INVALID_HINT_TEXT,
    UserRoutingService,
)


class DummyConversationService:
    def __init__(self, latest_rewrite_state=None):
        self._latest_rewrite_state = latest_rewrite_state

    def get_latest_rewrite_state(self, conversation_id: str):
        return self._latest_rewrite_state


def test_stream_route_or_reply_returns_no_document_reply_when_exact_rewrite_has_no_history(monkeypatch):
    service = UserRoutingService(conversation_service=DummyConversationService())

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_chunk:
            callbacks.on_chunk("rewrite")
        return "rewrite"

    monkeypatch.setattr(
        "backend.services.user_routing_service.stream_llm_completion",
        _fake_stream_llm_completion,
    )

    decision = asyncio.run(
        service.stream_route_or_reply(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "请帮我修改这一段内容"}],
            latest_user_message="请帮我修改这一段内容",
            model_provider="deepseek",
        )
    )

    assert decision.route == "reply"
    assert decision.reply_text == NO_DOCUMENT_HINT_TEXT
    assert decision.reply_streamed is False


def test_stream_route_or_reply_returns_rewrite_when_output_is_exact_literal(monkeypatch):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_chunk:
            callbacks.on_chunk("rewrite")
        return "rewrite"

    monkeypatch.setattr(
        "backend.services.user_routing_service.stream_llm_completion",
        _fake_stream_llm_completion,
    )

    decision = asyncio.run(
        service.stream_route_or_reply(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "把上一版第三章写得更正式"}],
            latest_user_message="把上一版第三章写得更正式",
            model_provider="deepseek",
        )
    )

    assert decision.route == "rewrite"
    assert decision.reply_text == ""


def test_stream_route_or_reply_flushes_prefix_buffer_once_reply_diverges(monkeypatch):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )
    emitted_chunks: list[str] = []

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        for chunk in ["re", "write您好", "，这里是答复。"]:
            if callbacks and callbacks.on_chunk:
                callbacks.on_chunk(chunk)
        return "rewrite您好，这里是答复。"

    monkeypatch.setattr(
        "backend.services.user_routing_service.stream_llm_completion",
        _fake_stream_llm_completion,
    )

    decision = asyncio.run(
        service.stream_route_or_reply(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "你好"}],
            latest_user_message="你好",
            model_provider="deepseek",
            on_reply_chunk=emitted_chunks.append,
        )
    )

    assert decision.route == "reply"
    assert emitted_chunks[0] == "rewrite您好"
    assert decision.reply_text == "rewrite您好，这里是答复。"
    assert decision.used_llm is True


def test_stream_route_or_reply_force_rewrite_returns_fixed_reply(monkeypatch):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_chunk:
            callbacks.on_chunk(REWRITE_INVALID_HINT_TEXT)
        return REWRITE_INVALID_HINT_TEXT

    monkeypatch.setattr(
        "backend.services.user_routing_service.stream_llm_completion",
        _fake_stream_llm_completion,
    )

    decision = asyncio.run(
        service.stream_route_or_reply(
            conversation_id="conv-1",
            messages=[{"role": "user", "content": "今天天气怎么样"}],
            latest_user_message="今天天气怎么样",
            model_provider="deepseek",
            force_rewrite=True,
        )
    )

    assert decision.route == "reply"
    assert decision.reply_text == REWRITE_INVALID_HINT_TEXT
