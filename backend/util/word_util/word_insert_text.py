"""Helpers for normalizing AI text before writing it back into Word."""

from __future__ import annotations

import re


WORD_MANUAL_LINE_BREAK = chr(11)


def normalize_word_insert_text(
    text: str, *, break_char: str = WORD_MANUAL_LINE_BREAK
) -> str:
    """Convert HTML or escaped line breaks into Word-compatible line breaks."""

    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = (
        normalized.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
    )
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", normalized)
    return normalized.replace("\n", break_char)


__all__ = ["WORD_MANUAL_LINE_BREAK", "normalize_word_insert_text"]
