"""Conversation-aware routing helpers for the unified user stream."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from backend.skills import SkillRegistry, get_skill_registry
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
from backend.util.log_util.rewrite_audit_log import (
    REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
    create_rewrite_audit_log,
    write_rewrite_audit_stage,
)

logger = logging.getLogger(__name__)

NO_DOCUMENT_HINT_TEXT = "当前会话没有可用文档，请先完成一次生成。"
NON_REWRITE_HINT_TEXT = "我这边暂时没收到有效回复，请重试一次。"


@dataclass(frozen=True)
class UserRouteDecision:
    route: str
    skill_id: Optional[str] = None
    latest_rewrite_state: Optional[Dict[str, Any]] = None
    reply_text: str = ""
    reply_streamed: bool = False
    used_llm: bool = False
    rewrite_log_path: Optional[str] = None


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
    def __init__(
        self,
        conversation_service: Optional[ConversationService] = None,
        skill_registry: Optional[SkillRegistry] = None,
    ):
        self._conversation_service = conversation_service or get_conversation_service()
        self._skill_registry = skill_registry or get_skill_registry()

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
        route_skill_summaries = self._skill_registry.list_skill_summaries()
        skill_ids = self._skill_registry.list_skill_ids()
        request_messages: list[dict[str, Any]] = []

        prefix_buffer = ""
        reply_parts: list[str] = []
        reply_started = False
        reply_streamed = False

        def _prefix_matches_registered_skill(prefix: str) -> bool:
            return any(skill_id.startswith(prefix) for skill_id in skill_ids)

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
            if prefix_buffer and _prefix_matches_registered_skill(prefix_buffer):
                return

            _emit_reply_text(prefix_buffer)
            prefix_buffer = ""

        def _capture_request_messages(items: list[dict[str, Any]]) -> None:
            request_messages.clear()
            request_messages.extend(dict(item) for item in items)

        rendered_prompt = render_route_or_reply_prompt(
            RouteOrReplyPromptInput(
                skills=route_skill_summaries,
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
            callbacks=StreamCallbacks(
                on_chunk=_handle_stream_chunk,
                on_request_messages=_capture_request_messages,
            ),
            timeout_seconds=30,
            check_interval=2.0,
        )

        logger.info(
            "user 路由输出完成: model=%s, output=%r",
            model_provider,
            raw_output,
        )

        normalized_output = str(raw_output or "").strip()
        if normalized_output in skill_ids:
            binding = self._skill_registry.get_executor_binding(normalized_output)
            rewrite_log_path = self._write_skill_directory_route_audit(
                conversation_id=conversation_id,
                request_messages=request_messages,
                rendered_system_prompt=rendered_prompt.system_prompt,
                rendered_user_prompt=rendered_prompt.user_prompt,
            )
            if binding.route_literal == REWRITE_ROUTE_LITERAL and not has_rewrite_history:
                return UserRouteDecision(
                    route=REPLY_ROUTE_LITERAL,
                    skill_id=normalized_output,
                    latest_rewrite_state=latest_rewrite_state,
                    reply_text=NO_DOCUMENT_HINT_TEXT,
                    used_llm=True,
                    rewrite_log_path=rewrite_log_path,
                )
            return UserRouteDecision(
                route=binding.route_literal,
                skill_id=normalized_output,
                latest_rewrite_state=latest_rewrite_state,
                used_llm=True,
                rewrite_log_path=rewrite_log_path,
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

    def _write_skill_directory_route_audit(
        self,
        *,
        conversation_id: str,
        request_messages: Sequence[Dict[str, Any]],
        rendered_system_prompt: str,
        rendered_user_prompt: str,
    ) -> Optional[str]:
        payload_messages = list(request_messages)
        if not payload_messages:
            payload_messages = []
            if rendered_system_prompt:
                payload_messages.append({"role": "system", "content": rendered_system_prompt})
            if rendered_user_prompt:
                payload_messages.append({"role": "user", "content": rendered_user_prompt})

        try:
            log_path = create_rewrite_audit_log(conversation_id)
            write_rewrite_audit_stage(
                log_path,
                REWRITE_STAGE_SKILL_DIRECTORY_ROUTE,
                payload_messages,
            )
            return log_path
        except Exception:
            logger.exception("写入 rewrite route 审计日志失败: conversation_id=%s", conversation_id)
            return None


_user_routing_service: Optional[UserRoutingService] = None


def get_user_routing_service() -> UserRoutingService:
    global _user_routing_service
    if _user_routing_service is None:
        _user_routing_service = UserRoutingService()
    return _user_routing_service
