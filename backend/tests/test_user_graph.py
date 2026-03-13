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
    def __init__(
        self,
        decision: UserRouteDecision | None = None,
        error: Exception | None = None,
        chunks: list[str] | None = None,
    ):
        self._decision = decision
        self._error = error
        self._chunks = chunks or []

    async def stream_route_or_reply(self, **kwargs):
        if self._error is not None:
            raise self._error
        on_reply_chunk = kwargs.get("on_reply_chunk")
        if callable(on_reply_chunk):
            for chunk in self._chunks:
                on_reply_chunk(chunk)
        return self._decision


class DocumentServiceStub:
    def __init__(self, response: GenerateResponse):
        self._response = response
        self.calls: list[dict] = []

    async def create_rewrite_task(self, **_kwargs):
        self.calls.append(dict(_kwargs))
        return self._response


async def _collect_lines(graph: UserGraph, state: dict) -> list[dict]:
    lines: list[dict] = []
    async for raw_line in graph.stream(DummyRequest(), state):
        lines.append(json.loads(raw_line))
    return lines


def test_user_graph_streams_reply_without_route_event():
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(success=True, task_id="unused", task_kind=TaskKind.REWRITE)
        ),
        routing_service=RoutingStub(
            UserRouteDecision(route="reply", reply_text="你好", reply_streamed=False)
        ),
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

    assert lines == [
        {"event": "chunk", "data": {"content": "你好"}},
        {"event": "done", "data": {"content": "你好"}},
    ]


def test_user_graph_preserves_streamed_reply_chunks():
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(success=True, task_id="unused", task_kind=TaskKind.REWRITE)
        ),
        routing_service=RoutingStub(
            UserRouteDecision(route="reply", reply_text="你好", reply_streamed=True),
            chunks=["你", "好"],
        ),
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

    assert lines == [
        {"event": "chunk", "data": {"content": "你"}},
        {"event": "chunk", "data": {"content": "好"}},
        {"event": "done", "data": {"content": "你好"}},
    ]


def test_user_graph_dispatches_rewrite_task_accepted():
    document_service = DocumentServiceStub(
        GenerateResponse(
            success=True,
            task_id="task-1",
            task_kind=TaskKind.REWRITE,
            status=TaskStatus.QUEUED,
            queue_position=1,
            waiting_count=2,
        )
    )
    graph = UserGraph(
        document_service=document_service,
        routing_service=RoutingStub(UserRouteDecision(route="rewrite")),
    )

    lines = asyncio.run(
        _collect_lines(
            graph,
            {
                "conversation_id": "conv-1",
                "model_provider": "deepseek",
                "messages": [{"role": "user", "content": "请帮我修改"}],
                "latest_user_message": "请帮我修改",
            },
        )
    )

    assert lines[0]["event"] == "route"
    assert lines[0]["data"]["route"] == "rewrite"
    assert lines[1]["event"] == "task_accepted"
    assert lines[1]["data"]["task_id"] == "task-1"
    assert lines[1]["data"]["task_kind"] == "rewrite"
    assert document_service.calls == [
        {
            "conversation_id": "conv-1",
            "user_prompt": "请帮我修改",
            "model_provider": "deepseek",
        }
    ]


def test_user_graph_falls_back_to_reply_when_rewrite_task_has_no_document():
    graph = UserGraph(
        document_service=DocumentServiceStub(
            GenerateResponse(
                success=False,
                task_id="unused",
                task_kind=TaskKind.REWRITE,
                message="当前会话没有可用文档，请先完成一次生成。",
                error="REWRITE_NO_DOCUMENT",
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
                "messages": [{"role": "user", "content": "请帮我修改"}],
                "latest_user_message": "请帮我修改",
            },
        )
    )

    assert lines == [
        {"event": "chunk", "data": {"content": "当前会话没有可用文档，请先完成一次生成。"}},
        {"event": "done", "data": {"content": "当前会话没有可用文档，请先完成一次生成。"}},
    ]


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
                "message": "统一路由回复超时，请稍后重试",
            },
        }
    ]
