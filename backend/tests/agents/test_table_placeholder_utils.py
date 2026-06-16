from __future__ import annotations

from backend.agents.generation.table_placeholder_utils import (
    build_missing_table_placeholder_findings,
    extract_table_placeholders,
    find_missing_table_placeholders,
)


def test_extract_table_placeholders_dedupes_in_first_occurrence_order() -> None:
    text = "前文 [[TABLE:TP1_1]]\n中间 [[TABLE:TP1_2]]\n重复 [[TABLE:TP1_1]]\n"

    assert extract_table_placeholders(text) == ["TP1_1", "TP1_2"]


def test_extract_table_placeholders_matches_inline_and_standalone_lines() -> None:
    text = (
        "| 序号 | 参数 |\n"
        "| --- | --- |\n"
        "| 1 | A |\n"
        "[[TABLE:TP1]]\n"
        "结尾另含 [[TABLE:TP2]] 占位符。"
    )

    assert extract_table_placeholders(text) == ["TP1", "TP2"]


def test_extract_table_placeholders_returns_empty_when_no_match() -> None:
    assert extract_table_placeholders("普通正文，没有占位符。") == []


def test_extract_table_placeholders_handles_none_and_non_string() -> None:
    assert extract_table_placeholders(None) == []
    assert extract_table_placeholders({"x": 1}) == []


def test_find_missing_table_placeholders_reports_absent_ids_in_param_order() -> None:
    tender_params = (
        "技术参数：\n"
        "| 序号 | 参数 |\n"
        "[[TABLE:TP1_1]]\n"
        "[[TABLE:TP1_2]]\n"
    )
    current_text = (
        "技术参数：\n"
        "| 序号 | 参数 |\n"
        "| 1 | A |\n"
        "[[TABLE:TP1_2]]\n"
    )

    assert find_missing_table_placeholders(tender_params, current_text) == ["TP1_1"]


def test_find_missing_table_placeholders_returns_empty_when_all_present() -> None:
    tender_params = "[[TABLE:TP1_1]]\n[[TABLE:TP1_2]]"
    current_text = "正文\n[[TABLE:TP1_2]]\n[[TABLE:TP1_1]]"

    assert find_missing_table_placeholders(tender_params, current_text) == []


def test_find_missing_table_placeholders_returns_empty_when_params_have_none() -> None:
    assert find_missing_table_placeholders(None, "正文") == []


def test_build_missing_table_placeholder_findings_emits_one_per_missing_id() -> None:
    findings = build_missing_table_placeholder_findings(["TP1_1", "TP1_2"])

    assert len(findings) == 2
    assert findings[0].evidence == (
        "技术参数包含结构化表占位符 [[TABLE:TP1_1]]，"
        "但待审核正文缺失该占位符。结构化表必须以占位符原样保留，"
        "不得改写为 Markdown/手绘表格或省略。"
    )
    assert findings[0].fix_hint == (
        "在对应位置补回占位符 [[TABLE:TP1_1]]，"
        "保持技术参数中该表的原始位置与上下文；不要手工重绘表格。"
    )
    assert findings[1].evidence == (
        "技术参数包含结构化表占位符 [[TABLE:TP1_2]]，"
        "但待审核正文缺失该占位符。结构化表必须以占位符原样保留，"
        "不得改写为 Markdown/手绘表格或省略。"
    )


def test_build_missing_table_placeholder_findings_drops_empty_ids() -> None:
    findings = build_missing_table_placeholder_findings(["", "TP1_1"])

    assert len(findings) == 1
    assert "TP1_1" in findings[0].evidence


def test_build_missing_table_placeholder_findings_returns_empty_for_empty_input() -> None:
    assert build_missing_table_placeholder_findings([]) == []
