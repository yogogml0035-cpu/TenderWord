"""Conversation runtime service.

In-memory conversation state for rewrite history and tab heartbeat tracking.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

MAX_REWRITE_MESSAGES = 6
CONVERSATION_STALE_SECONDS = 60 * 60 * 6
SERVICE_INSTANCE_ID = f"{os.getpid()}-{uuid.uuid4().hex[:10]}"


@dataclass
class RewriteMessage:
    role: str
    content: str
    rewrite_state: Optional[Dict[str, Any]] = None
    model: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class ConversationRuntime:
    conversation_id: str
    rewrite_messages: List[RewriteMessage] = field(default_factory=list)
    last_heartbeat_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)


class ConversationService:
    """Manage conversation-scoped runtime state in memory."""

    def __init__(self):
        self._lock = threading.RLock()
        self._conversations: Dict[str, ConversationRuntime] = {}

    def heartbeat(self, conversation_id: str) -> Dict[str, Any]:
        """Refresh conversation activity and return instance snapshot."""
        now = time.time()
        with self._lock:
            runtime = self._conversations.get(conversation_id)
            if runtime is None:
                runtime = ConversationRuntime(conversation_id=conversation_id)
                self._conversations[conversation_id] = runtime

            runtime.last_heartbeat_at = now
            runtime.last_activity_at = now
            self._cleanup_stale_locked(now=now)

        return {
            "conversation_id": conversation_id,
            "alive": True,
            "instance_id": SERVICE_INSTANCE_ID,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "rewrite_available": self.has_rewrite_history(conversation_id),
        }

    def get_latest_rewrite_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            runtime = self._conversations.get(conversation_id)
            if runtime is None:
                return None

            for item in reversed(runtime.rewrite_messages):
                if item.role == "assistant" and isinstance(item.rewrite_state, dict):
                    return dict(item.rewrite_state)
        return None

    def list_rewrite_states(self, conversation_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            runtime = self._conversations.get(conversation_id)
            if runtime is None:
                return []

            items: List[Dict[str, Any]] = []
            for entry in runtime.rewrite_messages:
                if entry.role == "assistant" and isinstance(entry.rewrite_state, dict):
                    items.append(dict(entry.rewrite_state))
            return items

    def list_rewrite_messages(self, conversation_id: str) -> List[RewriteMessage]:
        with self._lock:
            runtime = self._conversations.get(conversation_id)
            if runtime is None:
                return []

            items: List[RewriteMessage] = []
            for entry in runtime.rewrite_messages:
                items.append(
                    RewriteMessage(
                        role=entry.role,
                        content=entry.content,
                        rewrite_state=dict(entry.rewrite_state)
                        if isinstance(entry.rewrite_state, dict)
                        else None,
                        model=entry.model,
                        created_at=entry.created_at,
                    )
                )
            return items

    def has_rewrite_history(self, conversation_id: str) -> bool:
        return self.get_latest_rewrite_state(conversation_id) is not None

    def seed_generate_success(
        self,
        conversation_id: str,
        rewrite_state: Dict[str, Any],
        *,
        model: Optional[str] = None,
    ) -> None:
        """Append one assistant rewrite_state entry after generate success."""
        now = time.time()
        message = RewriteMessage(
            role="assistant",
            content="generate_success",
            rewrite_state=dict(rewrite_state),
            model=model,
            created_at=now,
        )
        with self._lock:
            runtime = self._ensure_runtime_locked(conversation_id, now=now)
            runtime.rewrite_messages.append(message)
            self._trim_messages_locked(runtime)

    def append_rewrite_success(
        self,
        conversation_id: str,
        *,
        user_prompt: str,
        rewrite_state: Dict[str, Any],
        model: Optional[str] = None,
    ) -> None:
        """Append Human + Assistant atomically after rewrite success."""
        self._append_revision_success(
            conversation_id,
            user_prompt=user_prompt,
            assistant_content="rewrite_success",
            rewrite_state=rewrite_state,
            model=model,
        )

    def append_edit_success(
        self,
        conversation_id: str,
        *,
        user_prompt: str,
        rewrite_state: Dict[str, Any],
        model: Optional[str] = None,
    ) -> None:
        """Append Human + Assistant atomically after edit success."""
        self._append_revision_success(
            conversation_id,
            user_prompt=user_prompt,
            assistant_content="edit_success",
            rewrite_state=rewrite_state,
            model=model,
        )

    def _append_revision_success(
        self,
        conversation_id: str,
        *,
        user_prompt: str,
        assistant_content: str,
        rewrite_state: Dict[str, Any],
        model: Optional[str] = None,
    ) -> None:
        """Append one revision turn and keep rewrite-state continuity."""
        now = time.time()
        user_message = RewriteMessage(
            role="user",
            content=user_prompt,
            rewrite_state=None,
            model=model,
            created_at=now,
        )
        ai_message = RewriteMessage(
            role="assistant",
            content=assistant_content,
            rewrite_state=dict(rewrite_state),
            model=model,
            created_at=now,
        )
        with self._lock:
            runtime = self._ensure_runtime_locked(conversation_id, now=now)
            runtime.rewrite_messages.extend([user_message, ai_message])
            self._trim_messages_locked(runtime)

    def _ensure_runtime_locked(
        self, conversation_id: str, *, now: Optional[float] = None
    ) -> ConversationRuntime:
        runtime = self._conversations.get(conversation_id)
        if runtime is None:
            runtime = ConversationRuntime(conversation_id=conversation_id)
            self._conversations[conversation_id] = runtime

        ts = now if now is not None else time.time()
        runtime.last_activity_at = ts
        runtime.last_heartbeat_at = ts
        return runtime

    def _trim_messages_locked(self, runtime: ConversationRuntime) -> None:
        if len(runtime.rewrite_messages) <= MAX_REWRITE_MESSAGES:
            return
        runtime.rewrite_messages = runtime.rewrite_messages[-MAX_REWRITE_MESSAGES:]

    def _cleanup_stale_locked(self, *, now: Optional[float] = None) -> None:
        ts = now if now is not None else time.time()
        stale_ids = [
            conversation_id
            for conversation_id, runtime in self._conversations.items()
            if ts - runtime.last_heartbeat_at > CONVERSATION_STALE_SECONDS
        ]
        for conversation_id in stale_ids:
            self._conversations.pop(conversation_id, None)


_conversation_service: Optional[ConversationService] = None


def get_conversation_service() -> ConversationService:
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service
