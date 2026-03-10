"""Conversation-aware routing helpers for the unified user stream."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence

from backend.services.conversation_service import ConversationService, get_conversation_service
from backend.util.common_util import StreamCallbacks, stream_llm_completion

logger = logging.getLogger(__name__)

REWRITE_ROUTE_LITERAL = "rewrite"
REPLY_ROUTE_LITERAL = "reply"

REWRITE_INVALID_HINT_TEXT = "当前不是有效的润色修改指令，请明确说明改哪段、改成什么效果。"
CHAT_REWRITE_SWITCH_HINT_TEXT = "当前问题更适合使用“润色修改”模式，请切换后再发送。"
DOC_CONTEXT_HINT_TEXT = (
    "当前不会自动携带文档正文，如需我分析具体内容，请粘贴相关段落；"
    "如果是想修改已生成的招标文件，请直接告诉我需要修改或重写的部分。"
)
NO_DOCUMENT_HINT_TEXT = "当前会话没有可用文档，请先完成一次生成。"
NON_REWRITE_HINT_TEXT = (
    "当前支持在生成招标文件后继续修改或重写，如果生成结果不满意，"
    "可以直接告诉我需要修改或重写的部分。"
)

REWRITE_PROMPT_RELEVANCE_SYSTEM_PROMPT = """
你是招标文档润色指令分类器。
你的任务是判断用户输入是否是在要求修改当前招标文档内容。

如果用户输入是在要求对当前文档进行润色、改写、补充、删除、替换、重写、调整、修订，输出 true。
如果用户输入是闲聊、提问、解释、总结、翻译、评价、问候、与文档修改无关的话题，输出 false。

规则：
1. 只能输出小写 true 或 false。
2. 不要输出解释、标点、JSON、代码块或任何额外文本。
3. 即使没有出现“润色”“修改”等明确关键词，只要语义上是在要求改当前文档，也输出 true。
4. 无法明确判断时，输出 false。
""".strip()

ROUTE_OR_REPLY_SYSTEM_PROMPT = """
你是东松招标文件智能生成助手。
如果用户输入和修改、润色、改写、重写已生成的招标文本有关，只输出 rewrite。
如果用户输入无关，就直接正常回答问题，并在合适时自然提醒用户：当前支持在生成招标文件后继续修改或重写，不满意时可以直接下达修改重写指令。
如果用户的问题依赖“当前文档”“这份文档”“第几章”等正文内容，但消息本身不是要求修改重写，不要假装看过文档；要直接说明当前不会自动携带文档正文，建议用户粘贴相关段落或直接下达修改重写指令。
如果用户是在打招呼、询问你是谁、你能做什么，请简短自我介绍，并明确自称“东松招标文件智能生成助手”。

规则：
1. 只有确定是修改、润色、改写、重写当前招标文本时，才能输出 rewrite。
2. 输出 rewrite 时只能输出这一个单词，小写，不得带任何额外字符。
3. 其他情况直接输出给用户的中文回复，不要输出 JSON、标签、解释、分析过程。
4. 如果不确定是否属于修改重写，按普通回复处理。
5. 对“支持生成后继续修改或重写”的提醒最多说一次，不要重复改写同一提醒。
""".strip()

FORCE_REWRITE_SYSTEM_PROMPT = f"""
你是东松招标文件智能生成助手。
如果用户输入是在要求修改、润色、改写、重写当前招标文本，只输出 rewrite。
如果不是有效的润色修改指令，就直接输出下面这句话，不得改写：
{REWRITE_INVALID_HINT_TEXT}

规则：
1. 命中润色修改时只能输出 rewrite。
2. 不命中时只能输出上面的固定提示语。
3. 不要输出解释、JSON、标签、额外标点或分析过程。
""".strip()

# Deprecated legacy heuristics, kept for /chat/stream compatibility only.
REWRITE_TOKENS = (
    "润色",
    "改写",
    "修改文档",
    "帮我改",
    "替换文案",
    "重写",
    "修订",
    "增补",
    "删掉",
    "删去",
    "去掉",
    "补充",
    "调整",
    "完善",
    "精简",
    "扩写",
    "压缩",
    "改成",
    "改为",
    "删除",
    "移除",
    "去除",
    "取消",
    "替换",
    "新增",
    "增加",
    "优化措辞",
)

STRUCTURED_EDIT_ACTION_TOKENS = (
    "删除",
    "移除",
    "去除",
    "取消",
    "删掉",
    "删去",
    "去掉",
    "替换",
    "改成",
    "改为",
    "修改为",
    "新增",
    "增加",
    "补充",
    "保留",
)

DOC_CONTEXT_TOKENS = (
    "当前文档",
    "这个文档",
    "刚生成的文档",
    "上一版文档",
    "你刚才生成",
    "文档内容",
    "全文",
    "第几章",
    "哪一章",
    "这份文档",
)


@dataclass(frozen=True)
class UserRouteDecision:
    route: str
    latest_rewrite_state: Optional[Dict[str, Any]] = None
    reply_text: str = ""
    reply_streamed: bool = False
    used_llm: bool = False


def looks_like_structured_edit_instruction(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    has_section_reference = bool(
        re.search(r"\b\d+(?:\.\d+){1,3}\b", lowered)
        or re.search(r"第[一二三四五六七八九十百零0-9]+[章节条款项]", lowered)
    )
    has_edit_action = any(token in lowered for token in STRUCTURED_EDIT_ACTION_TOKENS)
    return has_section_reference and has_edit_action


def looks_like_rewrite_intent(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in REWRITE_TOKENS) or looks_like_structured_edit_instruction(
        lowered
    )


def looks_like_doc_context_query(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in DOC_CONTEXT_TOKENS)


class UserRoutingService:
    def __init__(self, conversation_service: Optional[ConversationService] = None):
        self._conversation_service = conversation_service or get_conversation_service()

    def _build_rewrite_relevance_user_prompt(
        self,
        *,
        prompt: str,
        latest_rewrite_state: Optional[Dict[str, Any]],
    ) -> str:
        if not latest_rewrite_state:
            return (
                "【用户输入】\n"
                f"{prompt}\n\n"
                "请判断该输入是否是在要求修改一份招标文档内容。"
                "只输出 true 或 false。"
            )

        project_number = str(latest_rewrite_state.get("project_number") or "").strip()
        project_name = str(latest_rewrite_state.get("project_name") or "").strip()
        tender_type = str(latest_rewrite_state.get("tender_type") or "").strip()
        polished_text = str(latest_rewrite_state.get("polished_text") or "").strip()
        polished_preview = re.sub(r"\s+", " ", polished_text)
        if len(polished_preview) > 600:
            polished_preview = polished_preview[:600] + "..."

        return (
            "【当前会话文档信息】\n"
            f"project_number={project_number}\n"
            f"project_name={project_name}\n"
            f"tender_type={tender_type}\n"
            f"latest_polished_preview={polished_preview}\n\n"
            "【用户输入】\n"
            f"{prompt}\n\n"
            "请判断该输入是否是在要求修改当前招标文档内容。"
            "只输出 true 或 false。"
        )

    def _build_route_user_prompt(
        self,
        *,
        messages: Sequence[Dict[str, str]],
        latest_user_message: str,
        latest_rewrite_state: Optional[Dict[str, Any]],
        has_rewrite_history: bool,
    ) -> str:
        history_lines: list[str] = []
        for item in messages[-6:]:
            role = "用户" if str(item.get("role") or "") == "user" else "助手"
            content = re.sub(r"\s+", " ", str(item.get("content") or "").strip())
            if not content:
                continue
            if len(content) > 300:
                content = content[:300] + "..."
            history_lines.append(f"{role}: {content}")

        history_block = "\n".join(history_lines) if history_lines else "（无历史对话）"
        doc_summary = "无"
        if latest_rewrite_state:
            project_number = str(latest_rewrite_state.get("project_number") or "").strip()
            project_name = str(latest_rewrite_state.get("project_name") or "").strip()
            tender_type = str(latest_rewrite_state.get("tender_type") or "").strip()
            polished_preview = re.sub(
                r"\s+",
                " ",
                str(latest_rewrite_state.get("polished_text") or "").strip(),
            )
            if len(polished_preview) > 400:
                polished_preview = polished_preview[:400] + "..."
            doc_summary = (
                f"project_number={project_number}\n"
                f"project_name={project_name}\n"
                f"tender_type={tender_type}\n"
                f"latest_polished_preview={polished_preview}"
            )

        return (
            "【会话状态】\n"
            f"has_rewrite_history={'yes' if has_rewrite_history else 'no'}\n\n"
            "【最近对话】\n"
            f"{history_block}\n\n"
            "【当前文档摘要】\n"
            f"{doc_summary}\n\n"
            "【最新用户消息】\n"
            f"{latest_user_message}\n"
        )

    async def is_rewrite_prompt_related(
        self,
        *,
        prompt: str,
        model_provider: str,
        latest_rewrite_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        normalized_prompt = str(prompt or "").strip()
        if not normalized_prompt:
            return False

        raw_output = await stream_llm_completion(
            model_provider=model_provider,
            system_prompt=REWRITE_PROMPT_RELEVANCE_SYSTEM_PROMPT,
            user_prompt=self._build_rewrite_relevance_user_prompt(
                prompt=normalized_prompt,
                latest_rewrite_state=latest_rewrite_state,
            ),
            extra_params_override={"temperature": 0.0, "max_tokens": 4},
            timeout_seconds=8,
            check_interval=2.0,
        )
        normalized_output = str(raw_output or "").strip().lower()
        logger.info(
            "rewrite 指令相关性校验完成: model=%s, output=%r, prompt=%r",
            model_provider,
            normalized_output,
            normalized_prompt,
        )
        return normalized_output == "true"

    async def stream_route_or_reply(
        self,
        *,
        conversation_id: str,
        messages: Sequence[Dict[str, str]],
        latest_user_message: str,
        model_provider: str,
        force_rewrite: bool = False,
        on_reply_chunk: Optional[Callable[[str], None]] = None,
    ) -> UserRouteDecision:
        normalized_message = str(latest_user_message or "").strip()
        latest_rewrite_state = self._conversation_service.get_latest_rewrite_state(conversation_id)
        has_rewrite_history = latest_rewrite_state is not None

        if force_rewrite and not has_rewrite_history:
            return UserRouteDecision(
                route=REPLY_ROUTE_LITERAL,
                latest_rewrite_state=latest_rewrite_state,
                reply_text=NO_DOCUMENT_HINT_TEXT,
            )

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

        raw_output = await stream_llm_completion(
            model_provider=model_provider,
            system_prompt=FORCE_REWRITE_SYSTEM_PROMPT if force_rewrite else ROUTE_OR_REPLY_SYSTEM_PROMPT,
            user_prompt=self._build_route_user_prompt(
                messages=messages,
                latest_user_message=normalized_message,
                latest_rewrite_state=latest_rewrite_state,
                has_rewrite_history=has_rewrite_history,
            ),
            callbacks=StreamCallbacks(on_chunk=_handle_stream_chunk),
            timeout_seconds=30,
            check_interval=2.0,
        )

        logger.info(
            "user 路由输出完成: model=%s, output=%r, force_rewrite=%s",
            model_provider,
            raw_output,
            force_rewrite,
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

    async def route_message(
        self,
        *,
        conversation_id: str,
        prompt: str,
        model_provider: str,
        force_rewrite: bool = False,
    ) -> UserRouteDecision:
        return await self.stream_route_or_reply(
            conversation_id=conversation_id,
            messages=[{"role": "user", "content": prompt}],
            latest_user_message=prompt,
            model_provider=model_provider,
            force_rewrite=force_rewrite,
        )


_user_routing_service: Optional[UserRoutingService] = None


def get_user_routing_service() -> UserRoutingService:
    global _user_routing_service
    if _user_routing_service is None:
        _user_routing_service = UserRoutingService()
    return _user_routing_service
