from __future__ import annotations

from typing import Any


def format_prompt_value(value: Any) -> str:
    """Render optional prompt values without leaking Python None literals."""
    if value is None:
        return ""
    return str(value)


__all__ = ["format_prompt_value"]
