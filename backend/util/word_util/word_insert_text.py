"""Helpers for normalizing AI text before writing it back into Word."""

from __future__ import annotations

import re


WORD_MANUAL_LINE_BREAK = chr(11)
WORD_PARAGRAPH_BREAK = "\r"


def _normalize_text_to_word_breaks(text: str, *, break_char: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = (
        normalized.replace("\\r\\n", "\n").replace("\\r", "\n").replace("\\n", "\n")
    )
    normalized = re.sub(r"(?i)<br\s*/?>", "\n", normalized)
    return normalized.replace("\n", break_char)


def normalize_word_body_text(text: str) -> str:
    """Normalize AI text for Word body content using paragraph breaks."""

    return _normalize_text_to_word_breaks(text, break_char=WORD_PARAGRAPH_BREAK)


def normalize_word_cell_text(text: str) -> str:
    """Normalize AI text for Word table-cell content."""

    return _normalize_text_to_word_breaks(text, break_char=WORD_PARAGRAPH_BREAK)


def normalize_word_insert_text(
    text: str, *, break_char: str = WORD_PARAGRAPH_BREAK
) -> str:
    """
    Backward-compatible normalizer.

    Body content now defaults to paragraph breaks. Callers that need explicit
    branches should prefer `normalize_word_body_text()` or
    `normalize_word_cell_text()`.
    """

    return _normalize_text_to_word_breaks(text, break_char=break_char)


__all__ = [
    "WORD_MANUAL_LINE_BREAK",
    "WORD_PARAGRAPH_BREAK",
    "normalize_word_body_text",
    "normalize_word_cell_text",
    "normalize_word_insert_text",
]
