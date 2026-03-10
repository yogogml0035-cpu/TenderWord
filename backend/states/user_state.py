"""UserGraph state definitions."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict


class UserGraphMessage(TypedDict):
    role: str
    content: str


class UserGraphState(TypedDict, total=False):
    conversation_id: str
    model_provider: str
    force_rewrite: bool
    messages: List[UserGraphMessage]
    latest_user_message: str
    route: str
    error_code: Optional[str]
    error_message: Optional[str]
    latest_rewrite_state: Optional[Dict[str, str]]
