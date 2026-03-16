"""UserGraph state definitions."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class UserGraphMessage(TypedDict):
    role: str
    content: str


class UserGraphState(TypedDict, total=False):
    conversation_id: str
    model_provider: str
    messages: List[UserGraphMessage]
    latest_user_message: str
    rewrite_log_path: Optional[str]
    route: str
    reply_text: str
    reply_streamed: bool
    latest_rewrite_state: Optional[Dict[str, str]]
