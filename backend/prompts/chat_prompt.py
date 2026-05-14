from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from backend.prompts.types import PlainChatMessage


PLAIN_CHAT_HISTORY_LIMIT = 6
PLAIN_CHAT_SYSTEM_PROMPT = (
    "你是东松招标文件智能生成助手。"
    "请用简洁、专业、诚实的中文回复。"
)
_ALLOWED_CHAT_ROLES = {"user", "assistant"}


def _get_message_value(message: Any, key: str) -> str:
    if isinstance(message, Mapping):
        return str(message.get(key) or "")
    return str(getattr(message, key, "") or "")


def normalize_plain_chat_messages(
    messages: Sequence[Any],
    *,
    limit: int = PLAIN_CHAT_HISTORY_LIMIT,
) -> list[PlainChatMessage]:
    normalized_messages: list[PlainChatMessage] = []
    for message in messages[-limit:]:
        role = _get_message_value(message, "role")
        content = _get_message_value(message, "content").strip()
        if role not in _ALLOWED_CHAT_ROLES or not content:
            continue
        normalized_messages.append(PlainChatMessage(role=role, content=content))
    return normalized_messages


def extract_latest_plain_chat_user_message(
    messages: Sequence[PlainChatMessage | Mapping[str, str]],
) -> str:
    for item in reversed(messages):
        role = item["role"] if isinstance(item, Mapping) else item.role
        if role != "user":
            continue
        return item["content"] if isinstance(item, Mapping) else item.content
    return ""


def render_plain_chat_messages(
    messages: Sequence[PlainChatMessage | Mapping[str, str]],
) -> list[dict[str, str]]:
    rendered_messages = [{"role": "system", "content": PLAIN_CHAT_SYSTEM_PROMPT}]
    for message in messages:
        if isinstance(message, Mapping):
            role = str(message.get("role") or "")
            content = str(message.get("content") or "")
        else:
            role = message.role
            content = message.content
        if role in _ALLOWED_CHAT_ROLES and content:
            rendered_messages.append({"role": role, "content": content})
    return rendered_messages
