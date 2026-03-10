"""Logical user routing graph for chat vs rewrite dispatch."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Optional

from backend.services.chat_stream_service import stream_chat_response, to_ndjson_line
from backend.services.user_routing_service import UserRoutingService, get_user_routing_service
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

    async def route_message(self, state: UserGraphState) -> UserGraphState:
        decision = await self._routing_service.route_message(
            conversation_id=str(state.get("conversation_id") or "").strip(),
            prompt=str(state.get("latest_user_message") or "").strip(),
            model_provider=str(state.get("model_provider") or "deepseek"),
            force_rewrite=bool(state.get("force_rewrite")),
        )
        next_state = dict(state)
        next_state.update(
            {
                "route": decision.route,
                "error_code": decision.error_code,
                "error_message": decision.error_message,
                "latest_rewrite_state": decision.latest_rewrite_state,
            }
        )
        return next_state

    async def chat_node(self, request: Any, state: UserGraphState) -> AsyncIterator[str]:
        yield to_ndjson_line("route", {"route": "chat"})
        async for line in stream_chat_response(
            request,
            conversation_id=str(state.get("conversation_id") or ""),
            model_provider=str(state.get("model_provider") or "deepseek"),
            normalized_messages=state.get("messages") or [],
        ):
            yield line

    async def rewrite_dispatch(self, state: UserGraphState) -> AsyncIterator[str]:
        yield to_ndjson_line("route", {"route": "rewrite"})

        if state.get("error_code"):
            yield to_ndjson_line(
                "error",
                {
                    "code": state.get("error_code"),
                    "message": state.get("error_message") or "路由失败",
                },
            )
            return

        response = await self._document_service.create_rewrite_task(
            conversation_id=str(state.get("conversation_id") or "").strip(),
            user_prompt=str(state.get("latest_user_message") or "").strip(),
            model_provider=str(state.get("model_provider") or "deepseek"),
        )
        if not response.success:
            yield to_ndjson_line(
                "error",
                {
                    "code": response.error or "REWRITE_FAILED",
                    "message": response.message or "润色任务创建失败",
                },
            )
            return

        yield to_ndjson_line(
            "task_accepted",
            {
                "task_id": response.task_id,
                "task_kind": response.task_kind.value
                if hasattr(response.task_kind, "value")
                else str(response.task_kind),
                "status": response.status.value if getattr(response.status, "value", None) else response.status,
                "queue_position": response.queue_position,
                "waiting_count": response.waiting_count,
            },
        )

    async def blocked_doc_context(self, state: UserGraphState) -> AsyncIterator[str]:
        yield to_ndjson_line("route", {"route": "blocked_doc_context"})
        yield to_ndjson_line(
            "error",
            {
                "code": state.get("error_code") or "CHAT_DOC_CONTEXT_REQUIRED",
                "message": state.get("error_message") or "当前会话不自动携带文档正文",
            },
        )

    async def stream(self, request: Any, state: UserGraphState) -> AsyncIterator[str]:
        try:
            next_state = await self.route_message(state)
        except LLMTimeoutError:
            yield to_ndjson_line(
                "error",
                {
                    "code": "LLM_TIMEOUT",
                    "message": "润色指令校验超时，请稍后重试",
                },
            )
            return
        except Exception:
            yield to_ndjson_line(
                "error",
                {
                    "code": "LLM_SERVICE_ERROR",
                    "message": "润色指令校验失败，请稍后重试",
                },
            )
            return

        route = next_state.get("route")
        if route == "rewrite":
            async for line in self.rewrite_dispatch(next_state):
                yield line
            return
        if route == "blocked_doc_context":
            async for line in self.blocked_doc_context(next_state):
                yield line
            return
        async for line in self.chat_node(request, next_state):
            yield line
