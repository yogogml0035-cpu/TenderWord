from __future__ import annotations

import pytest

from backend.helper.word_helper.clause_marker_normalize import (
    CANONICAL_STAR,
    CANONICAL_TRIANGLE,
    STAR_MARKERS,
    TRIANGLE_MARKERS,
    build_marker_correction_comments,
    normalize_clause_markers,
    normalize_table_models_markers,
)


@pytest.mark.parametrize(
    "src, expected",
    [
        ("△1.1.1.4 管仓设计", "▲1.1.1.4 管仓设计"),
        ("*5.1 原厂保修", "★5.1 原厂保修"),
        ("※验收要求", "★验收要求"),
        ("Δ3.1.1 接口：USB", "▲3.1.1 接口：USB"),
        ("1、△产品形态：一体", "1、▲产品形态：一体"),
        ("1.1 *保修要求", "1.1 ★保修要求"),
        ("2）※验收标准", "2）★验收标准"),
        ("（1）△关键参数", "（1）▲关键参数"),
    ],
)
def test_normalize_clause_markers_replaces_at_clause_positions(src: str, expected: str) -> None:
    out, changes = normalize_clause_markers(src)
    assert out == expected
    assert changes
    assert all(old != new for old, new in changes)


def test_normalize_cell_internal_newline() -> None:
    src = "单元格内换行\n※验收要求"
    out, changes = normalize_clause_markers(src)
    assert out == "单元格内换行\n★验收要求"
    assert len(changes) == 1


def test_normalize_does_not_touch_technical_symbols() -> None:
    src = "温升 ΔT 不超过 5℃；尺寸 5*6；型号 ABC*01；3.1*5 无分隔"
    out, changes = normalize_clause_markers(src)
    assert out == src
    assert changes == []


def test_already_canonical_produces_no_change() -> None:
    src = "▲1.1.1.4 管仓设计\n★5.1 原厂保修"
    out, changes = normalize_clause_markers(src)
    assert out == src
    assert changes == []


def test_all_triangle_variants_map_to_black_triangle() -> None:
    for ch in sorted(TRIANGLE_MARKERS):
        if ch == CANONICAL_TRIANGLE:
            continue
        src = f"{ch}1.2 条款"
        out, changes = normalize_clause_markers(src)
        assert out == f"{CANONICAL_TRIANGLE}1.2 条款", ch
        assert changes


def test_all_star_variants_map_to_black_star() -> None:
    for ch in sorted(STAR_MARKERS):
        if ch == CANONICAL_STAR:
            continue
        src = f"{ch}2.3 条款"
        out, changes = normalize_clause_markers(src)
        assert out == f"{CANONICAL_STAR}2.3 条款", ch
        assert changes


def test_duplicate_markers_each_produce_change() -> None:
    src = "△1.1 A\n△1.2 B"
    out, changes = normalize_clause_markers(src)
    assert out == "▲1.1 A\n▲1.2 B"
    assert len(changes) == 2


def test_build_marker_correction_comments() -> None:
    comments = build_marker_correction_comments([("△1.1 A", "▲1.1 A")])
    assert comments == [
        {
            "reference_text": "▲1.1 A",
            "comment_text": '原技术参数为“△1.1 A”，现改为“▲1.1 A”',
        }
    ]


def test_normalize_table_models_markers() -> None:
    models = [
        {
            "table_id": "TP1",
            "rows": 1,
            "cols": 1,
            "cells": [
                {
                    "row": 1,
                    "col": 1,
                    "row_span": 1,
                    "col_span": 1,
                    "text": "△1.1 参数\n*2 要求",
                }
            ],
        }
    ]
    out, changes = normalize_table_models_markers(models)
    assert out[0]["cells"][0]["text"] == "▲1.1 参数\n★2 要求"
    assert len(changes) == 2
