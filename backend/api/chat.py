"""Plain chat streaming API routes."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.util.common_util.llm_stream_utils import MODEL_CONFIGS, ensure_llm_env

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

MINIMAL_CHAT_SYSTEM_PROMPT = "你是一个简洁、专业、诚实的中文助手。"

REWRITE_HINT_TEXT = "当前问题更适合使用“润色修改”模式，请切换后再发送。"
DOC_CONTEXT_HINT_TEXT = "当前会话不自动携带文档正文，请切到“润色修改”或手动粘贴相关内容。"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"] = Field(..., description="消息角色")
    content: str = Field(..., min_length=1, description="消息文本")


class ChatStreamRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="会话ID")
    model: Literal["deepseek", "qwen", "doubao"] = Field(
        default="deepseek", description="模型类型"
    )
    messages: List[ChatMessage] = Field(default_factory=list, description="聊天历史消息")


def _build_error_detail(code: str, message: str) -> Dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _looks_like_rewrite_intent(text: str) -> bool:
    lowered = text.lower()
    rewrite_tokens = (
        "润色",
        "改写",
        "修改文档",
        "帮我改",
        "替换文案",
        "重写",
        "修订",
        "增补",
        "删掉",
    )
    return any(token in lowered for token in rewrite_tokens)


def _looks_like_doc_context_query(text: str) -> bool:
    lowered = text.lower()
    context_tokens = (
        "当前文档",
        "这个文档",
        "刚生成的文档",
        "上一版文档",
        "你刚才生成",
        "文档内容",
        "全文",
    )
    return any(token in lowered for token in context_tokens)


def _to_ndjson_line(event: str, data: Dict[str, Any]) -> str:
    return json.dumps({"event": event, "data": data}, ensure_ascii=False) + "\n"


@router.post(
    "/stream",
    summary="普通聊天流式接口",
    description="返回 NDJSON 流，事件类型至少包含 chunk / done / error。",
)
async def stream_chat(request: Request, payload: ChatStreamRequest) -> StreamingResponse:
    if not payload.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail("REQ_MISSING_FIELD", "messages 不能为空"),
        )

    normalized_messages: List[Dict[str, str]] = []
    for message in payload.messages[-6:]:
        content = message.content.strip()
        if not content:
            continue
        normalized_messages.append({"role": message.role, "content": content})

    if not normalized_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail("REQ_MISSING_FIELD", "messages 不能为空"),
        )

    latest_user_message = ""
    for item in reversed(normalized_messages):
        if item["role"] == "user":
            latest_user_message = item["content"]
            break

    if _looks_like_doc_context_query(latest_user_message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail("CHAT_DOC_CONTEXT_REQUIRED", DOC_CONTEXT_HINT_TEXT),
        )
    if _looks_like_rewrite_intent(latest_user_message):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_build_error_detail("CHAT_MODE_REQUIRES_REWRITE", REWRITE_HINT_TEXT),
        )

    model_provider = payload.model
    ensure_llm_env(model_provider)
    model_config = MODEL_CONFIGS.get(model_provider, MODEL_CONFIGS["deepseek"])
    llm_config = settings.get_llm_config(model_provider)

    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model_name = llm_config.get("model")
    if not api_key or not base_url or not model_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_build_error_detail("LLM_SERVICE_ERROR", "模型配置不完整"),
        )

    request_messages = [{"role": "system", "content": MINIMAL_CHAT_SYSTEM_PROMPT}]
    request_messages.extend(normalized_messages)

    async def event_generator():
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            max_retries=0,
        )
        full_parts: List[str] = []
        create_params: Dict[str, Any] = {
            "model": model_name,
            "messages": request_messages,
            "stream": True,
            **model_config.extra_params,
        }
        if model_config.stream_options:
            create_params["stream_options"] = model_config.stream_options
        if model_config.extra_body:
            create_params["extra_body"] = model_config.extra_body

        try:
            completion = await client.chat.completions.create(**create_params)
            async for chunk in completion:
                if await request.is_disconnected():
                    return
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                text = getattr(delta, "content", None)
                if not text:
                    continue
                full_parts.append(text)
                yield _to_ndjson_line("chunk", {"content": text})

            yield _to_ndjson_line("done", {"content": "".join(full_parts)})
        except asyncio.CancelledError:
            logger.info("chat stream cancelled by client: conversation_id=%s", payload.conversation_id)
            return
        except Exception as exc:
            logger.exception("chat stream failed: conversation_id=%s", payload.conversation_id)
            yield _to_ndjson_line(
                "error",
                {
                    "code": "CHAT_STREAM_ERROR",
                    "message": str(exc) or "聊天流失败",
                },
            )

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

