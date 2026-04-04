"""Task skill graph state definitions."""

from __future__ import annotations

from typing import Dict, List, Optional, TypedDict

from .base_state import TenderGraphStateBase


class RewriteHistoryMessage(TypedDict, total=False):
    role: str
    content: str
    created_at: float
    rewrite_state: Dict[str, str]


class TaskSkillGraphState(TenderGraphStateBase, total=False):
    skill_id: str
    conversation_id: str
    rewrite_mode: bool
    rewrite_user_prompt: str
    edit_user_prompt: str
    rewrite_base_text: str
    rewrite_target_index: int
    rewrite_history_messages: List[RewriteHistoryMessage]
    source_prepared_doc_path: str
    source_origin_tender_path: str
    rewrite_temp_output_path: str
    current_node_display_override: Optional[str]
