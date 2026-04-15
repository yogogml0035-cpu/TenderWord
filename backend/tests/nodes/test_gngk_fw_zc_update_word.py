from __future__ import annotations

import pytest

from backend.nodes.gngk_word_nodes.gngk_fw_zc_update_word import (
    _refresh_protected_fields,
    _convert_lines_to_items,
    _require_all_protected_fields,
    _resolve_block4_insert_start,
    _validate_block_window,
    split_polished_text_into_blocks,
)
from backend.helper.word_helper.cleanup_ops import is_effectively_empty_text
from backend.util.word_util import wdWithInTable


def test_split_polished_text_into_blocks_splits_service_three_field_flow() -> None:
    polished_text = "\n".join(
        [
            "一、服务概述",
            "服务地点：上海院区",
            "1. 驻场时间覆盖工作日",
            "服务期限: 12个月",
            "| 序号 | 内容 |",
            "| --- | --- |",
            "| 1 | 巡检 |",
            "付款方式：按季度结算",
            "七、其他补充要求",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["service_location_value"] == "上海院区"
    assert result["service_term_value"] == "12个月"
    assert result["payment_value"] == "按季度结算"
    assert result["block1"] == ["一、服务概述"]
    assert result["block2"] == ["1. 驻场时间覆盖工作日"]
    assert result["block3"] == [
        "| 序号 | 内容 |",
        "| --- | --- |",
        "| 1 | 巡检 |",
    ]
    assert result["block4"] == ["七、其他补充要求"]


def test_split_polished_text_into_blocks_rejects_missing_or_out_of_order_fields() -> None:
    with pytest.raises(ValueError, match="缺少关键字段: 服务期限："):
        split_polished_text_into_blocks(
            "\n".join(
                [
                    "服务地点：上海院区",
                    "付款方式：按季度结算",
                ]
            )
        )

    with pytest.raises(ValueError, match="顺序必须为 服务地点： -> 服务期限： -> 付款方式："):
        split_polished_text_into_blocks(
            "\n".join(
                [
                    "服务期限：12个月",
                    "服务地点：上海院区",
                    "付款方式：按季度结算",
                ]
            )
        )


def test_require_all_protected_fields_raises_when_service_field_missing() -> None:
    with pytest.raises(ValueError, match="缺少关键受保护字段: 服务期限："):
        _require_all_protected_fields(
            {
                "服务地点：": object(),
                "付款方式：": object(),
            }
        )


def test_split_polished_text_into_blocks_keeps_service_fields_and_places_rest_in_block4() -> None:
    polished_text = "\n".join(
        [
            "一、项目概述",
            "1、项目名称：复旦大学附属华山医院院本部1号楼急诊改扩建区域风机盘管空气过滤器更换及设备保养",
            "2、服务地点：复旦大学附属华山医院院本部1号楼急诊改扩建区域",
            "3、服务期限：2026年6月16日-2029年6月15日",
            "4、付款方式：",
            "11)前三季度维保费用按季度结算。",
            "四、服务内容及要求",
            "| 序号 | 检 查 项 目 |",
            "| --- | --- |",
            "| 01 | 检查或清洗室内机盘管翅片 |",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["block1"] == [
        "一、项目概述",
        "1、项目名称：复旦大学附属华山医院院本部1号楼急诊改扩建区域风机盘管空气过滤器更换及设备保养",
    ]
    assert result["service_location_value"] == "复旦大学附属华山医院院本部1号楼急诊改扩建区域"
    assert result["service_term_value"] == "2026年6月16日-2029年6月15日"
    assert result["payment_value"] == ""
    assert result["block2"] == []
    assert result["block3"] == []
    assert result["block4"] == [
        "11)前三季度维保费用按季度结算。",
        "四、服务内容及要求",
        "| 序号 | 检 查 项 目 |",
        "| --- | --- |",
        "| 01 | 检查或清洗室内机盘管翅片 |",
    ]


def test_split_polished_text_into_blocks_ignores_table_header_keyword_hits() -> None:
    polished_text = "\n".join(
        [
            "| 序号 | 服务项 | 服务期限 |",
            "| --- | --- | --- |",
            "一、服务概述",
            "2、服务地点：上海院区",
            "3、服务期限：12个月",
            "4、付款方式：按季度结算",
            "七、其他补充要求",
        ]
    )

    result = split_polished_text_into_blocks(polished_text)

    assert result["service_location_line"] == "2、服务地点：上海院区"
    assert result["service_term_line"] == "3、服务期限：12个月"
    assert result["payment_method_line"] == "4、付款方式：按季度结算"
    assert result["service_term_value"] == "12个月"
    assert result["block1"] == [
        "| 序号 | 服务项 | 服务期限 |",
        "| --- | --- | --- |",
        "一、服务概述",
    ]
    assert result["block2"] == []
    assert result["block3"] == []
    assert result["block4"] == ["七、其他补充要求"]


def test_convert_lines_to_items_turns_markdown_table_into_table_item() -> None:
    items = _convert_lines_to_items(
        [
            "11)前三季度维保费用按季度结算。",
            "| 序号 | 检 查 项 目 |",
            "| --- | --- |",
            "| 01 | 检查或清洗室内机盘管翅片 |",
        ]
    )

    assert items[0] == {"type": "text", "line": "11)前三季度维保费用按季度结算。"}
    assert items[1]["type"] == "table"
    assert items[1]["rows"] == [
        ["序号", "检 查 项 目"],
        ["01", "检查或清洗室内机盘管翅片"],
    ]


def test_strict_block_helpers_reject_invalid_windows_and_after_anchor_overflow() -> None:
    with pytest.raises(ValueError, match="服务期限与付款方式之间字段区间非法"):
        _validate_block_window(20, 10, label="服务期限与付款方式之间")

    with pytest.raises(ValueError, match="付款方式字段位置超出插入边界"):
        _resolve_block4_insert_start(101, 100)


def test_is_effectively_empty_text_treats_page_break_artifacts_as_empty() -> None:
    assert is_effectively_empty_text("\r\n\x0c\u200b")
    assert not is_effectively_empty_text("第四章 合同条款")


class _FakeRange:
    def __init__(self, start: int, end: int, text: str, *, in_table: bool = False):
        self.Start = start
        self.End = end
        self.Text = text
        self._in_table = in_table

    def Information(self, code: int) -> int:
        if code == wdWithInTable:
            return -1 if self._in_table else 0
        return 0


class _FakeParagraph:
    def __init__(self, rng: _FakeRange):
        self.Range = rng


class _FakeParagraphCollection:
    def __init__(self, paragraphs):
        self._paragraphs = list(paragraphs)

    def __iter__(self):
        return iter(self._paragraphs)


class _FakeDoc:
    def __init__(self, lines: list[tuple[str, bool]]):
        self._paragraphs = []
        cursor = 0
        for text, in_table in lines:
            start = cursor
            end = start + max(len(text), 1) + 1
            self._paragraphs.append(
                _FakeParagraph(_FakeRange(start, end, text, in_table=in_table))
            )
            cursor = end

    def Range(self, start: int, end: int):
        start_i = int(start)
        end_i = int(end)
        paragraphs = []
        for para in self._paragraphs:
            p_start = int(para.Range.Start)
            p_end = int(para.Range.End)
            if p_end < start_i:
                continue
            if p_start > end_i:
                continue
            paragraphs.append(para)
        return type("_FakeRangeView", (), {"Paragraphs": _FakeParagraphCollection(paragraphs)})()


def test_refresh_protected_fields_fails_fast_when_only_fuzzy_hits_exist() -> None:
    doc = _FakeDoc(
        [
            ("| 序号 | 服务项 | 服务期限 |", False),
            ("本项目服务期限：12个月", False),
            ("服务地点：上海院区", False),
            ("付款方式：按季度结算", False),
        ]
    )

    with pytest.raises(ValueError, match="缺少关键受保护字段: 服务期限："):
        _refresh_protected_fields(
            doc=doc,
            markers=["服务地点：", "服务期限：", "付款方式："],
            range_start=0,
            range_end=10_000,
            existing_fields={},
        )
