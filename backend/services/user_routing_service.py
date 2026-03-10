"""Conversation-aware routing and rewrite intent classification."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from backend.services.conversation_service import ConversationService, get_conversation_service
from backend.util.common_util import stream_llm_completion

logger = logging.getLogger(__name__)

REWRITE_INVALID_HINT_TEXT = "当前输入不属于可执行的润色指令"
CHAT_REWRITE_SWITCH_HINT_TEXT = "当前问题更适合使用“润色修改”模式，请切换后再发送。"
DOC_CONTEXT_HINT_TEXT = "当前会话不自动携带文档正文，请切到“润色修改”或手动粘贴相关内容。"
NO_DOCUMENT_HINT_TEXT = "当前会话没有可用文档，请先完成一次生成"

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

POTENTIAL_REWRITE_TOKENS = (
    "这段",
    "那段",
    "这一段",
    "上一版",
    "前一版",
    "上个版本",
    "版本",
    "更正式",
    "更专业",
    "更简洁",
    "更完整",
    "语气",
    "措辞",
    "补一句",
    "补一段",
    "删一段",
    "加一段",
    "补一下",
    "改一下",
    "星号",
    "指标前",
    "指标后",
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

PLAIN_CHAT_TOKENS = (
    "你好",
    "hello",
    "hi",
    "谢谢",
    "你是谁",
    "解释一下",
    "介绍一下",
    "什么是",
    "是什么意思",
    "为什么",
    "怎么",
    "如何",
    "翻译",
    "举个例子",
)


@dataclass(frozen=True)
class UserRouteDecision:
    route: str
    latest_rewrite_state: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    used_llm: bool = False


def looks_like_rewrite_intent(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in REWRITE_TOKENS) or looks_like_structured_edit_instruction(
        lowered
    )


def looks_like_potential_rewrite(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in POTENTIAL_REWRITE_TOKENS)


def looks_like_structured_edit_instruction(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    has_section_reference = bool(
        re.search(r"\b\d+(?:\.\d+){1,3}\b", lowered)
        or re.search(r"第[一二三四五六七八九十百零0-9]+[章节条款项]", lowered)
    )
    has_edit_action = any(token in lowered for token in STRUCTURED_EDIT_ACTION_TOKENS)
    return has_section_reference and has_edit_action


def looks_like_doc_context_query(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in DOC_CONTEXT_TOKENS)


def looks_like_plain_chat(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    return any(token in lowered for token in PLAIN_CHAT_TOKENS)


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

    async def route_message(
        self,
        *,
        conversation_id: str,
        prompt: str,
        model_provider: str,
        force_rewrite: bool = False,
    ) -> UserRouteDecision:
        normalized_prompt = str(prompt or "").strip()
        latest_rewrite_state = self._conversation_service.get_latest_rewrite_state(conversation_id)
        has_rewrite_history = latest_rewrite_state is not None

        if force_rewrite:
            if not has_rewrite_history:
                return UserRouteDecision(
                    route="rewrite",
                    error_code="REWRITE_NO_DOCUMENT",
                    error_message=NO_DOCUMENT_HINT_TEXT,
                )
            is_related = await self.is_rewrite_prompt_related(
                prompt=normalized_prompt,
                model_provider=model_provider,
                latest_rewrite_state=latest_rewrite_state,
            )
            if not is_related:
                return UserRouteDecision(
                    route="rewrite",
                    latest_rewrite_state=latest_rewrite_state,
                    error_code="REWRITE_PROMPT_INVALID",
                    error_message=REWRITE_INVALID_HINT_TEXT,
                    used_llm=True,
                )
            return UserRouteDecision(
                route="rewrite",
                latest_rewrite_state=latest_rewrite_state,
                used_llm=True,
            )

        if looks_like_doc_context_query(normalized_prompt) and not looks_like_rewrite_intent(
            normalized_prompt
        ):
            return UserRouteDecision(
                route="blocked_doc_context",
                latest_rewrite_state=latest_rewrite_state,
                error_code="CHAT_DOC_CONTEXT_REQUIRED",
                error_message=DOC_CONTEXT_HINT_TEXT,
            )

        if looks_like_rewrite_intent(normalized_prompt):
            if not has_rewrite_history:
                return UserRouteDecision(
                    route="rewrite",
                    error_code="REWRITE_NO_DOCUMENT",
                    error_message=NO_DOCUMENT_HINT_TEXT,
                )
            return UserRouteDecision(route="rewrite", latest_rewrite_state=latest_rewrite_state)

        should_use_llm = looks_like_potential_rewrite(normalized_prompt)
        if should_use_llm:
            is_related = await self.is_rewrite_prompt_related(
                prompt=normalized_prompt,
                model_provider=model_provider,
                latest_rewrite_state=latest_rewrite_state,
            )
            if is_related:
                if not has_rewrite_history:
                    return UserRouteDecision(
                        route="rewrite",
                        error_code="REWRITE_NO_DOCUMENT",
                        error_message=NO_DOCUMENT_HINT_TEXT,
                        used_llm=True,
                    )
                return UserRouteDecision(
                    route="rewrite",
                    latest_rewrite_state=latest_rewrite_state,
                    used_llm=True,
                )

        if looks_like_doc_context_query(normalized_prompt):
            return UserRouteDecision(
                route="blocked_doc_context",
                latest_rewrite_state=latest_rewrite_state,
                error_code="CHAT_DOC_CONTEXT_REQUIRED",
                error_message=DOC_CONTEXT_HINT_TEXT,
                used_llm=should_use_llm,
            )

        if looks_like_plain_chat(normalized_prompt) or not should_use_llm:
            return UserRouteDecision(
                route="chat",
                latest_rewrite_state=latest_rewrite_state,
                used_llm=should_use_llm,
            )

        return UserRouteDecision(route="chat", latest_rewrite_state=latest_rewrite_state, used_llm=True)


_user_routing_service: Optional[UserRoutingService] = None


def get_user_routing_service() -> UserRoutingService:
    global _user_routing_service
    if _user_routing_service is None:
        _user_routing_service = UserRoutingService()
    return _user_routing_service
