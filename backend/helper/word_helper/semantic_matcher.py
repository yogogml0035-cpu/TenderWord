"""
共享语义匹配工具。

从批注复制等场景抽取出统一的文本规范化与近似匹配逻辑，
供 edit 样式回填、comment copy 等共享复用。
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

_NUMBER_PREFIX_RE = re.compile(
    r"""
    ^\s*
    (?:
        第?[0-9一二三四五六七八九十百千]+(?:章|节|条|项)
        |
        [（(]?\s*[0-9一二三四五六七八九十]+(?:\.[0-9]+)*\s*[)）]?\s*[、.．:]
        |
        [A-Za-z]\s*[、.．)]
        |
        [一二三四五六七八九十]+\s*[、.．:]
    )
    \s*
    """,
    re.VERBOSE,
)

_PUNCT_OR_SPACE_RE = re.compile(
    r"""[\s\u00a0\u3000,，.。:：;；、!?！？"'“”‘’`~\-—_·•/\\|()（）\[\]【】<>《》]+"""
)


def strip_number_prefix(text: Optional[str]) -> str:
    """去掉句段起始的常见编号前缀。"""
    return _NUMBER_PREFIX_RE.sub("", str(text or ""), count=1)


def clean_semantic_text(text: Optional[str]) -> str:
    """保留语义内容，去掉 Word 控制字符并统一换行。"""
    if not text:
        return ""

    cleaned = (
        str(text)
        .replace("\x07", "")
        .replace("\ufeff", "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\v", "\n")
        .replace("\u00a0", " ")
    )
    return cleaned.strip()


def normalize_semantic_text(text: Optional[str]) -> str:
    """移除编号前缀、空白与常见标点，便于做保守语义匹配。"""
    cleaned = clean_semantic_text(text)
    if not cleaned:
        return ""

    normalized_lines: list[str] = []
    for raw_line in cleaned.split("\n"):
        line = str(raw_line or "")
        line = strip_number_prefix(line)
        line = _PUNCT_OR_SPACE_RE.sub("", line)
        if line:
            normalized_lines.append(line.lower())

    return "".join(normalized_lines)


def semantic_similarity_norm(normalized_a: str, normalized_b: str) -> float:
    """对已经规范化的文本做相似度计算。"""
    na = str(normalized_a or "")
    nb = str(normalized_b or "")
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0

    max_len = max(len(na), len(nb))
    min_len = min(len(na), len(nb))
    if max_len == 0:
        return 1.0

    len_ratio = min_len / max_len
    if len_ratio < 0.35:
        return 0.0

    if max_len <= 160:
        return SequenceMatcher(None, na, nb).ratio()

    def _bigrams(value: str) -> set[str]:
        if len(value) < 2:
            return {value} if value else set()
        return {value[index : index + 2] for index in range(len(value) - 1)}

    left = _bigrams(na)
    right = _bigrams(nb)
    if not left or not right:
        return 0.0

    intersection = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return (intersection / union) * len_ratio


def semantic_similarity(text_a: Optional[str], text_b: Optional[str]) -> float:
    """对原始文本做 normalize 后的近似匹配。"""
    return semantic_similarity_norm(
        normalize_semantic_text(text_a),
        normalize_semantic_text(text_b),
    )


__all__ = [
    "clean_semantic_text",
    "strip_number_prefix",
    "normalize_semantic_text",
    "semantic_similarity",
    "semantic_similarity_norm",
]
