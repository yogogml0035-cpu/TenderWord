"""Conversation-aware routing helpers for the unified user stream."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from backend.prompts.routing_prompt import (
    REPLY_ROUTE_LITERAL,
    REWRITE_ROUTE_LITERAL,
    render_route_or_reply_prompt,
)
from backend.prompts.types import (
    RewriteStateSnapshot,
    RouteHistoryMessage,
    RouteOrReplyPromptInput,
)
from backend.services.conversation_service import ConversationService, get_conversation_service
from backend.util.common_util import StreamCallbacks, stream_llm_completion

logger = logging.getLogger(__name__)

NO_DOCUMENT_HINT_TEXT = "当前会话没有可用文档，请先完成一次生成。"
NON_REWRITE_HINT_TEXT = "我这边暂时没收到有效回复，请重试一次。"


@dataclass(frozen=True)
class UserRouteDecision:
    route: str
    latest_rewrite_state: Optional[Dict[str, Any]] = None
    reply_text: str = ""
    reply_streamed: bool = False
    used_llm: bool = False


def _to_route_history_messages(
    messages: Sequence[Dict[str, str]],
) -> list[RouteHistoryMessage]:
    return [
        RouteHistoryMessage(
            role=str(item.get("role") or ""),
            content=str(item.get("content") or ""),
        )
        for item in messages
    ]


class UserRoutingService:
    def __init__(self, conversation_service: Optional[ConversationService] = None):
        self._conversation_service = conversation_service or get_conversation_service()

    async def stream_route_or_reply(
        self,
        *,
        conversation_id: str,
        messages: Sequence[Dict[str, str]],
        latest_user_message: str,
        model_provider: str,
        on_reply_chunk: Optional[Callable[[str], None]] = None,
    ) -> UserRouteDecision:
        normalized_message = str(latest_user_message or "").strip()
        latest_rewrite_state = self._conversation_service.get_latest_rewrite_state(conversation_id)
        latest_rewrite_snapshot = RewriteStateSnapshot.from_mapping(latest_rewrite_state)
        has_rewrite_history = latest_rewrite_state is not None

        prefix_buffer = ""
        reply_parts: list[str] = []
        reply_started = False
        reply_streamed = False

        def _emit_reply_text(text: str) -> None:
            nonlocal reply_started, reply_streamed
            if not text:
                return
            reply_started = True
            reply_parts.append(text)
            if on_reply_chunk:
                reply_streamed = True
                on_reply_chunk(text)

        def _handle_stream_chunk(chunk_text: str) -> None:
            nonlocal prefix_buffer
            if not chunk_text:
                return

            if reply_started:
                _emit_reply_text(chunk_text)
                return

            prefix_buffer += chunk_text
            if (
                len(prefix_buffer) <= len(REWRITE_ROUTE_LITERAL)
                and REWRITE_ROUTE_LITERAL.startswith(prefix_buffer)
            ):
                return

            _emit_reply_text(prefix_buffer)
            prefix_buffer = ""

        rendered_prompt = render_route_or_reply_prompt(
            RouteOrReplyPromptInput(
                messages=_to_route_history_messages(messages),
                latest_user_message=normalized_message,
                latest_rewrite_state=latest_rewrite_snapshot,
                has_rewrite_history=has_rewrite_history,
            )
        )
        raw_output = await stream_llm_completion(
            model_provider=model_provider,
            system_prompt=rendered_prompt.system_prompt,
            user_prompt=rendered_prompt.user_prompt,
            callbacks=StreamCallbacks(on_chunk=_handle_stream_chunk),
            timeout_seconds=30,
            check_interval=2.0,
        )

        logger.info(
            "user 路由输出完成: model=%s, output=%r",
            model_provider,
            raw_output,
        )

        if raw_output == REWRITE_ROUTE_LITERAL:
            if not has_rewrite_history:
                return UserRouteDecision(
                    route=REPLY_ROUTE_LITERAL,
                    latest_rewrite_state=latest_rewrite_state,
                    reply_text=NO_DOCUMENT_HINT_TEXT,
                )
            return UserRouteDecision(
                route=REWRITE_ROUTE_LITERAL,
                latest_rewrite_state=latest_rewrite_state,
                used_llm=True,
            )

        if prefix_buffer:
            _emit_reply_text(prefix_buffer)
            prefix_buffer = ""

        reply_text = "".join(reply_parts) if reply_parts else str(raw_output or "").strip()
        if not reply_text:
            reply_text = NON_REWRITE_HINT_TEXT

        if reply_streamed:
            reply_text = "".join(reply_parts)

        return UserRouteDecision(
            route=REPLY_ROUTE_LITERAL,
            latest_rewrite_state=latest_rewrite_state,
            reply_text=reply_text,
            reply_streamed=reply_streamed,
            used_llm=True,
        )


_user_routing_service: Optional[UserRoutingService] = None


def get_user_routing_service() -> UserRoutingService:
    global _user_routing_service
    if _user_routing_service is None:
        _user_routing_service = UserRoutingService()
    return _user_routing_service
