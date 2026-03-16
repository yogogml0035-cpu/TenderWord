from __future__ import annotations

import asyncio
import json
from pathlib import Path

import backend.util.log_util.rewrite_audit_log as rewrite_audit_log_module
from backend.services.user_routing_service import (
    NON_REWRITE_HINT_TEXT,
    NO_DOCUMENT_HINT_TEXT,
    UserRoutingService,
)
from backend.util.log_util.rewrite_audit_log import REWRITE_STAGE_ROUTE_OR_REPLY


class DummyConversationService:
    def __init__(self, latest_rewrite_state=None):
        self._latest_rewrite_state = latest_rewrite_state

    def get_latest_rewrite_state(self, conversation_id: str):
        return self._latest_rewrite_state


def _set_rewrite_log_root(monkeypatch, tmp_path: Path) -> Path:
    fake_module_path = tmp_path / "backend" / "util" / "log_util" / "rewrite_audit_log.py"
    fake_module_path.parent.mkdir(parents=True, exist_ok=True)
    fake_module_path.touch()
    monkeypatch.setattr(rewrite_audit_log_module, "__file__", str(fake_module_path))
    return tmp_path / "backend" / "prompts_log" / "rewrite_log"


def test_stream_route_or_reply_returns_no_document_reply_when_exact_rewrite_has_no_history(
    monkeypatch, tmp_path
):
    service = UserRoutingService(conversation_service=DummyConversationService())
    audit_dir = _set_rewrite_log_root(monkeypatch, tmp_path)
    request_messages = [
        {"role": "system", "content": "system-route"},
        {"role": "user", "content": "user-route"},
    ]

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_request_messages:
            callbacks.on_request_messages(request_messages)
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
    assert decision.rewrite_log_path
    payload = json.loads(Path(decision.rewrite_log_path).read_text(encoding="utf-8"))
    assert payload[REWRITE_STAGE_ROUTE_OR_REPLY] == request_messages
    assert len(list(audit_dir.glob("*.json"))) == 1


def test_stream_route_or_reply_returns_rewrite_when_output_is_exact_literal(monkeypatch, tmp_path):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )
    _set_rewrite_log_root(monkeypatch, tmp_path)
    request_messages = [
        {"role": "system", "content": "route-system"},
        {"role": "user", "content": "route-user"},
    ]

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_request_messages:
            callbacks.on_request_messages(request_messages)
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
    assert decision.rewrite_log_path
    payload = json.loads(Path(decision.rewrite_log_path).read_text(encoding="utf-8"))
    assert payload[REWRITE_STAGE_ROUTE_OR_REPLY] == request_messages


def test_stream_route_or_reply_flushes_prefix_buffer_once_reply_diverges(monkeypatch, tmp_path):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )
    emitted_chunks: list[str] = []
    audit_dir = _set_rewrite_log_root(monkeypatch, tmp_path)

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
    assert decision.rewrite_log_path is None
    assert not list(audit_dir.glob("*.json"))


def test_stream_route_or_reply_uses_service_fallback_when_model_returns_empty(monkeypatch, tmp_path):
    latest_rewrite_state = {"project_name": "示例项目", "polished_text": "原始内容"}
    service = UserRoutingService(
        conversation_service=DummyConversationService(latest_rewrite_state=latest_rewrite_state)
    )
    audit_dir = _set_rewrite_log_root(monkeypatch, tmp_path)

    async def _fake_stream_llm_completion(*_args, callbacks=None, **_kwargs):
        if callbacks and callbacks.on_chunk:
            callbacks.on_chunk("")
        return ""

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
        )
    )

    assert decision.route == "reply"
    assert decision.reply_text == NON_REWRITE_HINT_TEXT
    assert decision.reply_streamed is False
    assert decision.rewrite_log_path is None
    assert not list(audit_dir.glob("*.json"))
