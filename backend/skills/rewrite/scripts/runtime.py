from __future__ import annotations

from typing import Mapping


def has_source_document(state: Mapping[str, object]) -> bool:
    if "source_document_path" not in state:
        return True
    path = state.get("source_document_path")
    return bool(path and str(path).strip())


def select_resolve_branch(state: Mapping[str, object]) -> str:
    if str(state.get("rewrite_source") or "").strip() == "uploaded_file":
        return "extract_rewrite_context"
    return "rewrite_text"


def select_comment_branch(state: Mapping[str, object]) -> str:
    if str(state.get("rewrite_source") or "").strip() == "uploaded_file":
        return "delete_section"
    return "get_rewrite_comments" if has_source_document(state) else "delete_section"


def estimate_total_nodes(initial_state: Mapping[str, object]) -> int:
    if str(initial_state.get("rewrite_source") or "").strip() == "uploaded_file":
        return 5
    return 5 if has_source_document(initial_state) else 4
