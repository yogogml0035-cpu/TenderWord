from __future__ import annotations

from typing import Mapping


def has_uploaded_origin_tender(state: Mapping[str, object]) -> bool:
    if "source_origin_tender_path" not in state:
        return True
    path = state.get("source_origin_tender_path")
    return bool(path and str(path).strip())


def select_comment_branch(state: Mapping[str, object]) -> str:
    return "get_rewrite_comments" if has_uploaded_origin_tender(state) else "delete_section"


def estimate_total_nodes(initial_state: Mapping[str, object]) -> int:
    return 5 if has_uploaded_origin_tender(initial_state) else 4
