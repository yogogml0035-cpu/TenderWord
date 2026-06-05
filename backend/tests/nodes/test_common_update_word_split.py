from __future__ import annotations

import pytest

from backend.nodes.common_word_nodes.update_word import (
    _resolve_pre_field_insert_pos,
    split_polished_text_into_blocks,
)


def test_split_polished_text_into_blocks_ignores_table_header_keyword_hits() -> None:
    polished_text = "\n".join(
        [
            "| 序号 | 产品名称 | 数量 | 交付日期 |",
            "| --- | --- | --- | --- |",
            "| 1 | 温控柜 | 2台 | 合同签订后30天 |",
            "一、补充说明",
            "2、交付日期: 合同签订后30天",
            "付款方式: 按季度结算",
            "二、售后服务要求",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["delivery_date_line"] == "2、交付日期：合同签订后30天"
    assert result["payment_method_line"] == "付款方式：按季度结算"
    assert result["delivery_value"] == "合同签订后30天"
    assert result["payment_value"] == "按季度结算"
    assert result["block1"] == [
        "| 序号 | 产品名称 | 数量 | 交付日期 |",
        "| --- | --- | --- | --- |",
        "| 1 | 温控柜 | 2台 | 合同签订后30天 |",
        "一、补充说明",
    ]
    assert result["block2"] == []
    assert result["block3"] == ["二、售后服务要求"]


def test_split_polished_text_into_blocks_fails_when_only_table_or_prose_contains_keyword() -> None:
    polished_text = "\n".join(
        [
            "| 序号 | 产品名称 | 数量 | 交付日期 |",
            "本项目交付日期：合同签订后30天",
            "付款方式：按季度结算",
        ]
    )

    with pytest.raises(ValueError, match="缺少关键字段: 交付日期："):
        split_polished_text_into_blocks(polished_text)


def test_split_polished_text_into_blocks_preserves_explicit_blank_lines() -> None:
    polished_text = "\n".join(
        [
            "一、补充说明",
            "交付日期：合同签订后30天",
            "",
            "付款方式：按季度结算",
            "",
            "",
            "二、售后服务要求",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["block1"] == ["一、补充说明"]
    assert result["block2"] == [""]
    assert result["block3"] == ["", "", "二、售后服务要求"]


def test_resolve_pre_field_insert_pos_repairs_then_rescans_before_field() -> None:
    field_start = 120
    prev_calls: list[int] = []

    def _get_field_start() -> int:
        return field_start

    def _find_prev(pos: int, *, max_lookback: int = 0) -> int | None:
        prev_calls.append(int(pos))
        return None if len(prev_calls) == 1 else 96

    def _repair() -> bool:
        nonlocal field_start
        field_start = 128
        return True

    pos = _resolve_pre_field_insert_pos(
        get_field_start=_get_field_start,
        find_prev_editable_pos=_find_prev,
        repair_before_field=_repair,
        field_name="交付日期",
    )

    assert pos == 96
    assert prev_calls == [120, 128]


def test_resolve_pre_field_insert_pos_rejects_position_after_field() -> None:
    with pytest.raises(ValueError, match="避免写入字段值区"):
        _resolve_pre_field_insert_pos(
            get_field_start=lambda: 120,
            find_prev_editable_pos=lambda pos, *, max_lookback=0: 121,
            repair_before_field=lambda: False,
            field_name="交付日期",
        )


def test_resolve_pre_field_insert_pos_uses_field_start_after_repair_when_scan_still_blocked() -> None:
    field_start = 120
    prev_calls: list[int] = []

    def _get_field_start() -> int:
        return field_start

    def _find_prev(pos: int, *, max_lookback: int = 0) -> int | None:
        prev_calls.append(int(pos))
        return None

    pos = _resolve_pre_field_insert_pos(
        get_field_start=_get_field_start,
        find_prev_editable_pos=_find_prev,
        repair_before_field=lambda: True,
        field_name="交付日期",
    )

    assert pos == 120
    assert prev_calls == [120, 120]
