"""Shared helpers for plain chat streaming endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import datetime, timezone
from typing import Any

import httpx
from openai import AsyncOpenAI

from backend.config.settings import settings
from backend.util.common_util.llm_stream_utils import MODEL_CONFIGS, ensure_llm_env

logger = logging.getLogger(__name__)

MINIMAL_CHAT_SYSTEM_PROMPT = (
    "你是东松招标文件智能生成助手。"
    "请用简洁、专业、诚实的中文回复。"
)


def build_error_detail(code: str, message: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": {"code": code, "message": message},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def to_ndjson_line(event: str, data: dict[str, Any]) -> str:
    return json.dumps({"event": event, "data": data}, ensure_ascii=False) + "\n"


def normalize_chat_messages(messages: Sequence[Any], limit: int = 6) -> list[dict[str, str]]:
    normalized_messages: list[dict[str, str]] = []
    for message in messages[-limit:]:
        role = (
            str(getattr(message, "role", "") or "")
            if not isinstance(message, dict)
            else str(message.get("role") or "")
        )
        content = (
            str(getattr(message, "content", "") or "").strip()
            if not isinstance(message, dict)
            else str(message.get("content") or "").strip()
        )
        if role not in {"user", "assistant"} or not content:
            continue
        normalized_messages.append({"role": role, "content": content})
    return normalized_messages


def extract_latest_user_message(messages: Sequence[dict[str, str]]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user":
            return str(item.get("content") or "")
    return ""


async def stream_chat_response(
    request: Any,
    *,
    conversation_id: str,
    model_provider: str,
    normalized_messages: Sequence[dict[str, str]],
) -> AsyncIterator[str]:
    ensure_llm_env(model_provider)
    model_config = MODEL_CONFIGS.get(model_provider, MODEL_CONFIGS["deepseek"])
    llm_config = settings.get_llm_config(model_provider)

    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    model_name = llm_config.get("model")
    if not api_key or not base_url or not model_name:
        yield to_ndjson_line(
            "error",
            {
                "code": "LLM_SERVICE_ERROR",
                "message": "模型配置不完整",
            },
        )
        return

    request_messages = [{"role": "system", "content": MINIMAL_CHAT_SYSTEM_PROMPT}]
    request_messages.extend(normalized_messages)

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=httpx.Timeout(30.0, connect=10.0),
        max_retries=0,
    )
    full_parts: list[str] = []
    create_params: dict[str, Any] = {
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
            yield to_ndjson_line("chunk", {"content": text})

        yield to_ndjson_line("done", {"content": "".join(full_parts)})
    except asyncio.CancelledError:
        logger.info("chat stream cancelled by client: conversation_id=%s", conversation_id)
        return
    except Exception as exc:
        logger.exception("chat stream failed: conversation_id=%s", conversation_id)
        yield to_ndjson_line(
            "error",
            {
                "code": "CHAT_STREAM_ERROR",
                "message": str(exc) or "聊天流失败",
            },
        )
