from __future__ import annotations

import re
from typing import Any, Iterable

from backend.agents.generation.types import AuditFinding

# 行内或独立行均可命中；捕获 table_id（与 util.word_util.table_models 的字符集保持一致）。
TABLE_PLACEHOLDER_EXTRACT_RE = re.compile(r"\[\[TABLE:([A-Za-z0-9_-]+)\]\]")


def extract_table_placeholders(text: Any) -> list[str]:
    """从任意文本中提取 `[[TABLE:<id>]]`，按首次出现顺序去重。"""
    raw = str(text or "")
    seen: set[str] = set()
    ordered: list[str] = []
    for match in TABLE_PLACEHOLDER_EXTRACT_RE.finditer(raw):
        table_id = match.group(1)
        if not table_id or table_id in seen:
            continue
        seen.add(table_id)
        ordered.append(table_id)
    return ordered


def find_missing_table_placeholders(
    tender_params: Any,
    target_text: Any,
) -> list[str]:
    """对比技术参数与待审核/最终正文，找出 target 中缺失的 table ids（保持技术参数顺序）。"""
    required = extract_table_placeholders(tender_params)
    if not required:
        return []
    present = set(extract_table_placeholders(target_text))
    return [table_id for table_id in required if table_id not in present]


def _build_missing_table_finding(table_id: str) -> AuditFinding:
    return AuditFinding(
        evidence=(
            f"技术参数包含结构化表占位符 [[TABLE:{table_id}]]，"
            f"但待审核正文缺失该占位符。结构化表必须以占位符原样保留，"
            f"不得改写为 Markdown/手绘表格或省略。"
        ),
        fix_hint=(
            f"在对应位置补回占位符 [[TABLE:{table_id}]]，"
            f"保持技术参数中该表的原始位置与上下文；不要手工重绘表格。"
        ),
    )


def build_missing_table_placeholder_findings(
    missing_ids: Iterable[str],
) -> list[AuditFinding]:
    """将缺失的 table ids 转换为 AuditFinding 列表。"""
    return [_build_missing_table_finding(table_id) for table_id in missing_ids if table_id]


__all__ = [
    "TABLE_PLACEHOLDER_EXTRACT_RE",
    "extract_table_placeholders",
    "find_missing_table_placeholders",
    "build_missing_table_placeholder_findings",
]
