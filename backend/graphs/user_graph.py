"""Unified user routing graph for reply or rewrite dispatch."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from backend.services.chat_stream_service import to_ndjson_line
from backend.services.user_routing_service import (
    REPLY_ROUTE_LITERAL,
    REWRITE_ROUTE_LITERAL,
    UserRoutingService,
    get_user_routing_service,
)
from backend.states.user_state import UserGraphState
from backend.util.common_util import LLMTimeoutError


class UserGraph:
    def __init__(
        self,
        *,
        document_service: Any,
        routing_service: Optional[UserRoutingService] = None,
    ):
        self._document_service = document_service
        self._routing_service = routing_service or get_user_routing_service()
        self._graph = None

    def build_graph(self) -> StateGraph:
        builder = StateGraph(UserGraphState)
        builder.add_node("route_or_reply", self.route_or_reply)
        builder.add_node("rewrite_dispatch", self.rewrite_dispatch)
        builder.add_edge(START, "route_or_reply")
        builder.add_conditional_edges(
            "route_or_reply",
            self._select_next_node,
            {
                REWRITE_ROUTE_LITERAL: "rewrite_dispatch",
                REPLY_ROUTE_LITERAL: END,
            },
        )
        builder.add_edge("rewrite_dispatch", END)
        return builder

    def compile(self):
        if self._graph is None:
            self._graph = self.build_graph().compile()
        return self._graph

    async def route_or_reply(self, state: UserGraphState, config=None) -> UserGraphState:
        stream_writer = self._get_stream_writer(config)
        reply_route_emitted = False

        def emit_reply_chunk(text: str) -> None:
            nonlocal reply_route_emitted
            if not reply_route_emitted:
                self._emit_event(stream_writer, "route", {"route": REPLY_ROUTE_LITERAL})
                reply_route_emitted = True
            self._emit_event(
                stream_writer,
                "chunk",
                {"content": text},
            )

        decision = await self._routing_service.stream_route_or_reply(
            conversation_id=str(state.get("conversation_id") or "").strip(),
            messages=state.get("messages") or [],
            latest_user_message=str(state.get("latest_user_message") or "").strip(),
            model_provider=str(state.get("model_provider") or "deepseek"),
            on_reply_chunk=emit_reply_chunk,
        )

        next_state = dict(state)
        next_state.update(
            {
                "route": decision.route,
                "reply_text": decision.reply_text,
                "reply_streamed": decision.reply_streamed,
                "latest_rewrite_state": decision.latest_rewrite_state,
            }
        )

        if decision.route != REWRITE_ROUTE_LITERAL:
            if not reply_route_emitted:
                self._emit_event(stream_writer, "route", {"route": REPLY_ROUTE_LITERAL})
            if decision.reply_text and not decision.reply_streamed:
                self._emit_event(stream_writer, "chunk", {"content": decision.reply_text})
            self._emit_event(stream_writer, "done", {"content": decision.reply_text})

        return next_state

    async def rewrite_dispatch(self, state: UserGraphState, config=None) -> UserGraphState:
        stream_writer = self._get_stream_writer(config)
        response = await self._document_service.create_rewrite_task(
            conversation_id=str(state.get("conversation_id") or "").strip(),
            user_prompt=str(state.get("latest_user_message") or "").strip(),
            model_provider=str(state.get("model_provider") or "deepseek"),
        )

        if not response.success:
            error_code = str(response.error or "REWRITE_FAILED")
            error_message = str(response.message or "修改任务创建失败")
            if error_code == "REWRITE_NO_DOCUMENT":
                self._emit_event(stream_writer, "route", {"route": REPLY_ROUTE_LITERAL})
                self._emit_event(stream_writer, "chunk", {"content": error_message})
                self._emit_event(stream_writer, "done", {"content": error_message})
                next_state = dict(state)
                next_state.update(
                    {
                        "route": REPLY_ROUTE_LITERAL,
                        "reply_text": error_message,
                        "reply_streamed": False,
                    }
                )
                return next_state

            self._emit_event(
                stream_writer,
                "error",
                {
                    "code": error_code,
                    "message": error_message,
                },
            )
            return dict(state)

        self._emit_event(stream_writer, "route", {"route": REWRITE_ROUTE_LITERAL})
        self._emit_event(
            stream_writer,
            "task_accepted",
            {
                "task_id": response.task_id,
                "task_kind": response.task_kind.value
                if hasattr(response.task_kind, "value")
                else str(response.task_kind),
                "status": response.status.value
                if getattr(response.status, "value", None)
                else response.status,
                "queue_position": response.queue_position,
                "waiting_count": response.waiting_count,
            },
        )
        return dict(state)

    def _select_next_node(self, state: UserGraphState) -> str:
        if state.get("route") == REWRITE_ROUTE_LITERAL:
            return REWRITE_ROUTE_LITERAL
        return REPLY_ROUTE_LITERAL

    def _get_stream_writer(self, config) -> Optional[Callable[[str, dict[str, Any]], None]]:
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        stream_writer = configurable.get("stream_writer")
        if callable(stream_writer):
            return stream_writer
        return None

    def _emit_event(
        self,
        stream_writer: Optional[Callable[[str, dict[str, Any]], None]],
        event: str,
        data: dict[str, Any],
    ) -> None:
        if stream_writer is None:
            return
        stream_writer(event, data)

    async def stream(self, request: Any, state: UserGraphState) -> AsyncIterator[str]:
        del request

        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()

        def stream_writer(event: str, data: dict[str, Any]) -> None:
            queue.put_nowait(to_ndjson_line(event, data))

        async def _run_graph() -> None:
            try:
                await self.compile().ainvoke(
                    state,
                    config={"configurable": {"stream_writer": stream_writer}},
                )
            except LLMTimeoutError:
                stream_writer(
                    "error",
                    {
                        "code": "LLM_TIMEOUT",
                        "message": "统一路由回复超时，请稍后重试",
                    },
                )
            except Exception:
                stream_writer(
                    "error",
                    {
                        "code": "LLM_SERVICE_ERROR",
                        "message": "统一路由回复失败，请稍后重试",
                    },
                )
            finally:
                queue.put_nowait(None)

        graph_task = asyncio.create_task(_run_graph())
        try:
            while True:
                line = await queue.get()
                if line is None:
                    break
                yield line
        finally:
            if not graph_task.done():
                graph_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await graph_task
