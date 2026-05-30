from __future__ import annotations

from typing import Mapping


def has_source_document(state: Mapping[str, object]) -> bool:
    if "source_document_path" not in state:
        return True
    path = state.get("source_document_path")
    return bool(path and str(path).strip())


def select_comment_branch(state: Mapping[str, object]) -> str:
    return "get_rewrite_comments" if has_source_document(state) else "delete_section"


def estimate_total_nodes(initial_state: Mapping[str, object]) -> int:
    return 5 if has_source_document(initial_state) else 4
