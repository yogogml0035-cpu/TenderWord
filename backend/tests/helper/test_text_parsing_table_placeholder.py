from __future__ import annotations

from backend.helper.word_helper.text_parsing import convert_lines_to_items

# 一个最小可恢复的结构化表 sidecar 模型（与 table_models.StructuredTableModel 对齐）。
_TABLE_MODEL_TP1 = {
    "table_id": "TP1",
    "rows": 2,
    "cols": 2,
    "cells": [
        {"row": 1, "col": 1, "row_span": 1, "col_span": 1, "text": "序号"},
        {"row": 1, "col": 2, "row_span": 1, "col_span": 1, "text": "参数"},
        {"row": 2, "col": 1, "row_span": 1, "col_span": 1, "text": "1"},
        {"row": 2, "col": 2, "row_span": 1, "col_span": 1, "text": "A"},
    ],
}


def test_bare_placeholder_without_sidecar_is_dropped_not_text() -> None:
    """未命中 sidecar 的 [[TABLE:id]] 是内部写回入口，静默丢弃，绝不作为可见文本。"""
    items = convert_lines_to_items(["[[TABLE:TP1_1]]"], structured_table_models=[])

    assert items == []


def test_placeholder_with_matching_sidecar_restores_structured_table() -> None:
    """命中 sidecar 的占位符恢复为真实结构化表。"""
    items = convert_lines_to_items(
        ["[[TABLE:TP1]]"],
        structured_table_models=[_TABLE_MODEL_TP1],
    )

    assert len(items) == 1
    assert items[0]["type"] == "structured_table"
    assert items[0]["table_id"] == "TP1"
    assert items[0]["table_model"]["table_id"] == "TP1"


def test_projection_table_followed_by_unmatched_placeholder_is_dropped() -> None:
    """占位符前的 Markdown 投影表无法匹配 sidecar 时，投影连同占位符整段丢弃。"""
    lines = [
        "| 序号 | 参数 |",
        "| --- | --- |",
        "| 1 | A |",
        "[[TABLE:TP1_9]]",  # 未提供 sidecar
    ]

    items = convert_lines_to_items(lines, structured_table_models=[])

    assert items == []


def test_projection_table_followed_by_matched_placeholder_restores_real_table() -> None:
    """占位符前的投影表后跟可恢复占位符时，用真实结构化表替代近似投影。"""
    lines = [
        "| 序号 | 参数 |",
        "| --- | --- |",
        "| 1 | A |",
        "[[TABLE:TP1]]",  # 命中 sidecar
    ]

    items = convert_lines_to_items(lines, structured_table_models=[_TABLE_MODEL_TP1])

    assert len(items) == 1
    assert items[0]["type"] == "structured_table"
    assert items[0]["table_id"] == "TP1"


def test_inline_table_placeholder_in_text_line_is_stripped() -> None:
    """行内残留的 [[TABLE:id]] token 是内部入口，从文本行中清除，不写入 Word。"""
    items = convert_lines_to_items(
        ["1、技术参数：A。[[TABLE:TP1_1]]"],
        structured_table_models=[],
    )

    assert len(items) == 1
    assert items[0]["type"] == "text"
    assert "[[TABLE:" not in items[0]["line"]
    assert "1、技术参数：A。" in items[0]["line"]


def test_independent_table_without_placeholder_is_kept_as_pipe_table() -> None:
    """既无占位符邻居又无 sidecar 匹配的独立表格按普通 pipe 表格输出。"""
    lines = [
        "| 设备 | 数量 |",
        "| --- | --- |",
        "| 主机 | 1 |",
    ]

    items = convert_lines_to_items(lines, structured_table_models=[])

    assert len(items) == 1
    assert items[0]["type"] == "table"
    assert items[0]["rows"][0] == ["设备", "数量"]


def test_plain_text_lines_become_text_items() -> None:
    """普通文本行正常转为 text item。"""
    items = convert_lines_to_items(["1、参数：A。", "2、参数：B。"])

    assert items == [
        {"type": "text", "line": "1、参数：A。"},
        {"type": "text", "line": "2、参数：B。"},
    ]


def test_final_word_items_never_contain_visible_table_placeholder() -> None:
    """覆盖写回链路：无论何种组合，最终 item 文本中都不会出现可见 [[TABLE:...]]。"""
    lines = [
        "好的，以下是内容。",  # sanitizer 会清，但写回层也应防御
        "1、参数：A。[[TABLE:TP1_1]]",  # 行内占位符
        "[[TABLE:TP1_2]]",  # 裸占位符，无 sidecar
        "2、参数：B。",
    ]

    items = convert_lines_to_items(lines, structured_table_models=[])

    for item in items:
        if item["type"] == "text":
            assert "[[TABLE:" not in item["line"]
        # 不应出现把占位符当文本或当普通表格的 item。
        assert item["type"] in {"text", "table", "structured_table"}
