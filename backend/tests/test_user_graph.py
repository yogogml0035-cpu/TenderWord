from __future__ import annotations

import asyncio
import json

from backend.graphs.user_graph import UserGraph
from backend.models.generate import GenerateResponse
from backend.models.task import TaskKind, TaskStatus
from backend.services.user_routing_service import UserRouteDecision
from backend.util.common_util import LLMTimeoutError


class DummyRequest:
    async def is_disconnected(self) -> bool:
        return False


class RoutingStub:
    def __init__(self, decision: UserRouteDecision | None = None, error: Exception | None = None):
        self._decision = decision
        self._error = error

    async def route_message(self, **_kwargs):
        if self._error is not None:
            raise self._error
        return self._decision


class DocumentServiceStub:
    def __init__(self, response: GenerateResponse):
        self._response = response

    async def create_rewrite_task(self, **_kwargs):
        return self._response


async def _collect_lines(graph: UserGraph, state: dict) -> list[dict]:
    lines: list[dict] = []
    async for raw_line in graph.stream(DummyRequest(), state):
        lines.append(json.loads(raw_line))
    return lines


def test_user_graph_streams_chat_route(monkeypatch):
    async def _fake_chat_stream(*_args, **_kwargs):
        yield json.dumps({"event": "chunk", "data": {"content": "你"}}) + "\n"
        yield json.dumps({"event": "done", "data": {"content": "你好"}}) + "\n"

    monkeypatch.setattr("backend.graphs.user_graph.stream_chat_response", _fake_chat_stream)
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(success=True, task_id="unused", task_kind=TaskKind.REWRITE)
        ),
        routing_service=RoutingStub(UserRouteDecision(route="chat")),
    )

    lines = asyncio.run(
        _collect_lines(
            graph,
            {
                "conversation_id": "conv-1",
                "model_provider": "deepseek",
                "messages": [{"role": "user", "content": "你好"}],
                "latest_user_message": "你好",
            },
        )
    )

    assert lines[0]["event"] == "route"
    assert lines[0]["data"]["route"] == "chat"
    assert lines[1]["event"] == "chunk"
    assert lines[2]["event"] == "done"


def test_user_graph_dispatches_rewrite_task_accepted():
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(
                success=True,
                task_id="task-1",
                task_kind=TaskKind.REWRITE,
                status=TaskStatus.QUEUED,
                queue_position=1,
                waiting_count=2,
            )
        ),
        routing_service=RoutingStub(UserRouteDecision(route="rewrite")),
    )

    lines = asyncio.run(
        _collect_lines(
            graph,
            {
                "conversation_id": "conv-1",
                "model_provider": "deepseek",
                "messages": [{"role": "user", "content": "请帮我润色"}],
                "latest_user_message": "请帮我润色",
            },
        )
    )

    assert lines[0]["event"] == "route"
    assert lines[0]["data"]["route"] == "rewrite"
    assert lines[1]["event"] == "task_accepted"
    assert lines[1]["data"]["task_id"] == "task-1"
    assert lines[1]["data"]["task_kind"] == "rewrite"


def test_user_graph_returns_doc_context_error():
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(success=True, task_id="unused", task_kind=TaskKind.REWRITE)
        ),
        routing_service=RoutingStub(
            UserRouteDecision(
                route="blocked_doc_context",
                error_code="CHAT_DOC_CONTEXT_REQUIRED",
                error_message="当前会话不自动携带文档正文，请切到“润色修改”或手动粘贴相关内容。",
            )
        ),
    )

    lines = asyncio.run(
        _collect_lines(
            graph,
            {
                "conversation_id": "conv-1",
                "model_provider": "deepseek",
                "messages": [{"role": "user", "content": "总结当前文档"}],
                "latest_user_message": "总结当前文档",
            },
        )
    )

    assert lines[0]["event"] == "route"
    assert lines[0]["data"]["route"] == "blocked_doc_context"
    assert lines[1]["event"] == "error"
    assert lines[1]["data"]["code"] == "CHAT_DOC_CONTEXT_REQUIRED"


def test_user_graph_returns_timeout_error_when_router_times_out():
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(success=True, task_id="unused", task_kind=TaskKind.REWRITE)
        ),
        routing_service=RoutingStub(error=LLMTimeoutError("deepseek", 8)),
    )

    lines = asyncio.run(
        _collect_lines(
            graph,
            {
                "conversation_id": "conv-1",
                "model_provider": "deepseek",
                "messages": [{"role": "user", "content": "把这段写得更正式"}],
                "latest_user_message": "把这段写得更正式",
            },
        )
    )

    assert lines == [
        {
            "event": "error",
            "data": {
                "code": "LLM_TIMEOUT",
                "message": "润色指令校验超时，请稍后重试",
            },
        }
    ]
