from __future__ import annotations

from backend.prompts.chat_prompt import (
    PLAIN_CHAT_HISTORY_LIMIT,
    PLAIN_CHAT_SYSTEM_PROMPT,
    extract_latest_plain_chat_user_message,
    normalize_plain_chat_messages,
    render_plain_chat_messages,
)


def test_normalize_plain_chat_messages_filters_and_limits_history() -> None:
    messages = [
        {"role": "system", "content": "ignore"},
        {"role": "user", "content": "  你好  "},
        {"role": "assistant", "content": ""},
        *[
            {"role": "assistant" if index % 2 else "user", "content": f"消息 {index}"}
            for index in range(PLAIN_CHAT_HISTORY_LIMIT + 2)
        ],
    ]

    normalized = normalize_plain_chat_messages(messages)

    assert len(normalized) == PLAIN_CHAT_HISTORY_LIMIT
    assert all(item.role in {"user", "assistant"} for item in normalized)
    assert normalized[0].content == "消息 2"


def test_render_plain_chat_messages_adds_system_prompt() -> None:
    normalized = normalize_plain_chat_messages([{"role": "user", "content": "你好"}])

    rendered = render_plain_chat_messages(normalized)

    assert rendered[0] == {"role": "system", "content": PLAIN_CHAT_SYSTEM_PROMPT}
    assert rendered[1] == {"role": "user", "content": "你好"}


def test_extract_latest_plain_chat_user_message() -> None:
    normalized = normalize_plain_chat_messages(
        [
            {"role": "user", "content": "旧问题"},
            {"role": "assistant", "content": "旧回答"},
            {"role": "user", "content": "新问题"},
        ]
    )

    assert extract_latest_plain_chat_user_message(normalized) == "新问题"
